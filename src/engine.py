"""
# Using SSH
async with asyncssh.connect("address") as conn:
	channel, engine = await conn.create_subprocess(chess.engine.UciProtocol, "/path/to/stockfish")
	await engine.initialise()

	... do stuff

# Arbitrary stop
with await engine.analysis(chess.Board() ...) as analysis:
	async for info in analysis:
		... stuff ...
		if ..
			break
"""
import sys
import time
import chess
import redis
import pickle
import asyncio
import colorama
import chess.pgn
import chess.engine
import redis.asyncio


ENGINE_CONFIG = {
	"Threads": 6,
	"Hash": 4096,
}
ENGINE_DEPTH = 5


def clear_cache(db: redis.Redis):
	keys_to_delete = db.keys("ask-magnus:*")
	if len(keys_to_delete) > 0:
		db.delete(*keys_to_delete)


async def evaluate(
	db: redis.asyncio.Redis,
	engine: chess.engine.UciProtocol,
	board: chess.Board,
	multipv:int=3
):
	key = f"ask-magnus:{board.fen()}:{engine.id}:{ENGINE_DEPTH}"
	limit = chess.engine.Limit(depth=ENGINE_DEPTH)
	if await db.exists(key):
		raw_data = await db.get(key)
		result = pickle.loads(raw_data)
	else:
		result = await engine.analyse(board, limit=limit, multipv=multipv)
		if multipv == 1:
			result = [result]
		# To pickle or not to pickle. Hm. Usually I would say no. Buuut, this
		# result object it's very well developed and all __repr__ are
		# reinstantiatable. So, I'll pickle. Fingers crossed.
		await db.set(key, pickle.dumps(result))
	return result


async def get_engine():
	# Get chess engine
	transport, engine = await chess.engine.popen_uci("/opt/homebrew/bin/stockfish")
	await engine.configure(ENGINE_CONFIG)
	return engine


async def get_db():
	# Get database connection
	db = await redis.asyncio.Redis()
	return db
