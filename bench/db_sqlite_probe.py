"""SQLite 실현성 실측 — 게이트웨이 세션·턴 저장이 SQLite로 견디는지 확인.

게이트웨이 DB 워크로드:
- 쓰기: 세션 생성 + `is_final`마다 턴 1건 append (저빈도)
- 읽기: 컨텍스트 조립 시 recent_turns(N)
- 핫패스(초벌 렌더·라이브 상태)는 Redis라 DB로 오지 않음

관건: 여러 세션이 동시에 턴을 쓸 때 "database is locked" 없이, 목표 지연 안에서
처리되는가. WAL + busy_timeout 구성으로 SQLAlchemy async(aiosqlite) 측정.

사용: uv run python bench/db_sqlite_probe.py
"""

from __future__ import annotations

import asyncio
import statistics as stats
import time
from pathlib import Path

from sqlalchemy import String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DB_PATH = Path("data/probe.db")


class Base(DeclarativeBase):
    pass


class TurnRow(Base):
    __tablename__ = "turns"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(40), index=True)
    turn_id: Mapped[int] = mapped_column()
    source: Mapped[str] = mapped_column(Text)
    final: Mapped[str] = mapped_column(Text)


def make_engine():
    """WAL + busy_timeout으로 동시 쓰기 대기(에러 대신)."""
    eng = create_async_engine(
        f"sqlite+aiosqlite:///{DB_PATH}",
        connect_args={"timeout": 5.0},  # busy_timeout 5s
    )

    from sqlalchemy import event

    @event.listens_for(eng.sync_engine, "connect")
    def _pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    return eng


async def writer(sm: async_sessionmaker[AsyncSession], sid: str, n: int,
                 lat: list[float], errs: list[str]) -> None:
    for t in range(n):
        start = time.perf_counter()
        try:
            async with sm() as s:
                s.add(TurnRow(session_id=sid, turn_id=t,
                              source=f"내일 회의를 오후로 옮겨도 될까요? ({t})",
                              final=f"Bisakah rapat dipindah ke sore? ({t})"))
                await s.commit()
            lat.append((time.perf_counter() - start) * 1000)
        except Exception as e:  # noqa: BLE001 — 측정용, 에러 종류 수집
            errs.append(type(e).__name__)


async def reader(sm: async_sessionmaker[AsyncSession], sid: str, n: int,
                 lat: list[float]) -> None:
    for _ in range(n):
        start = time.perf_counter()
        async with sm() as s:
            await s.execute(
                select(TurnRow).where(TurnRow.session_id == sid)
                .order_by(TurnRow.turn_id.desc()).limit(5)
            )
        lat.append((time.perf_counter() - start) * 1000)


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[max(0, min(len(xs) - 1, round(p / 100 * (len(xs) - 1))))] if xs else float("nan")


async def scenario(sessions: int, turns_per: int, with_readers: bool) -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    DB_PATH.parent.mkdir(exist_ok=True)
    eng = make_engine()
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(eng, expire_on_commit=False)

    wlat: list[float] = []
    rlat: list[float] = []
    errs: list[str] = []
    tasks = [writer(sm, f"s{i}", turns_per, wlat, errs) for i in range(sessions)]
    if with_readers:
        tasks += [reader(sm, f"s{i}", turns_per, rlat) for i in range(sessions)]

    start = time.perf_counter()
    await asyncio.gather(*tasks)
    wall = time.perf_counter() - start
    await eng.dispose()

    total_w = sessions * turns_per
    label = f"{sessions} 세션 × {turns_per} 턴 동시" + (" +동시읽기" if with_readers else "")
    print(f"\n[{label}]")
    print(f"  쓰기 {total_w}건 / {wall*1000:.0f}ms → {total_w/wall:,.0f} writes/s")
    print(f"  쓰기 지연 p50={pct(wlat,50):.1f}ms p95={pct(wlat,95):.1f}ms "
          f"max={max(wlat):.1f}ms")
    if rlat:
        print(f"  읽기 지연 p50={pct(rlat,50):.1f}ms p95={pct(rlat,95):.1f}ms")
    print(f"  lock/에러: {len(errs)}건" + (f" {set(errs)}" if errs else " ✅"))


async def main() -> None:
    print("=" * 60)
    print("SQLite 실현성 — SQLAlchemy async + aiosqlite + WAL")
    print("=" * 60)
    await scenario(sessions=10, turns_per=20, with_readers=False)   # 저부하
    await scenario(sessions=50, turns_per=20, with_readers=False)   # 중부하 동시쓰기
    await scenario(sessions=50, turns_per=20, with_readers=True)    # 읽기·쓰기 혼합
    await scenario(sessions=200, turns_per=10, with_readers=True)   # 과부하(현실 초과)
    if DB_PATH.exists():
        DB_PATH.unlink()
    for ext in ("-wal", "-shm"):
        p = DB_PATH.with_name(DB_PATH.name + ext)
        if p.exists():
            p.unlink()


if __name__ == "__main__":
    asyncio.run(main())
