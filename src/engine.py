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
import pickle
import asyncio
import colorama
import chess.pgn
import chess.engine
import redis.asyncio
import redis.asyncio


PGN_PATH = "data/lichess.pgn"
ENGINE_CONFIG = {
	"Threads": 6,
	"Hash": 4096,
}
ENGINE_DEPTH = 5


def pretty_fen(fen):
	pretty_pieces = {
		'k': '♚',
		'q': '♛',
		'r': '♜',
		'b': '♝',
		'n': '♞',
		'p': '♟︎',
		'K': '♔',
		'Q': '♕',
		'R': '♖',
		'B': '♗',
		'N': '♘',
		'P': '♙'
	}
	board = fen.split(' ')[0]
	text = ''
	global is_white
	is_white = True

	def next_tile(contents):
		global is_white
		bg = colorama.Back.WHITE if is_white else colorama.Back.CYAN
		is_white = not is_white
		return bg + contents + ' ' + colorama.Back.RESET

	for letter in board:
		if letter == '/':
			text += '\n'
			is_white = not is_white
		elif letter.isdigit():
			text += ''.join([next_tile(' ') for _ in range(int(letter))])
		else:
			text += next_tile(colorama.Fore.BLACK + pretty_pieces[letter] + colorama.Fore.RESET)
	return colorama.Style.NORMAL  + text + colorama.Style.RESET_ALL


def clear_cache(db: redis.Redis):
	keys_to_delete = db.keys("ask-magnus:*")
	if len(keys_to_delete) > 0:
		db.delete(*keys_to_delete)


async def evaluate(
	engine: chess.engine.UciProtocol,
	db: redis.asyncio.Redis,
	board: chess.Board,
	multipv:int=3
):
	key = f"ask-magnus:{board.fen()}:{engine.id}:{ENGINE_DEPTH}"
	limit = chess.engine.Limit(depth=ENGINE_DEPTH)
	if not await db.exists(key):
		result = await engine.analyse(board, limit=limit, multipv=multipv)
		if multipv == 1:
			result = [result]
		# To pickle or not to pickle. Hm. Usually I would say no. Buuut, this
		# result object it's very well developed and all __repr__ are
		# reinstantiatable. So, I'll pickle. Fingers crossed.
		await db.set(key, pickle.dumps(result))
		return result
	else:
		raw_data = await db.get(key)
		return pickle.loads(raw_data)


async def main(limit_games=None):
	pgn = open(PGN_PATH)
	game_counter = 1
	first_print = True
	
	# Get chess engine
	transport, engine = await chess.engine.popen_uci("/opt/homebrew/bin/stockfish")
	await engine.configure(ENGINE_CONFIG)

	# Get database connection
	db = await redis.asyncio.Redis()

	while game := chess.pgn.read_game(pgn):
		board = game.board()
		for move in game.mainline_moves():
			if not first_print:
				sys.stdout.write("\033[11A")
			else:
				first_print = False
			board.push(move)
			start = time.time()
			evaluation = await evaluate(engine, db, board)
			end = time.time()
			print(colorama.Fore.BLUE + f'Game {game_counter}' + colorama.Fore.RESET)
			print(pretty_fen(board.fen()))
			print(f" Time to evaluate: {end - start:.2f} seconds")
			text = f" Evaluation: {evaluation[0]['score']}"
			if not (board.is_stalemate() or board.is_checkmate()):
				top_moves = []
				for line in evaluation:
					if board.is_stalemate() or board.is_checkmate():
						break
					if len(line['pv']) > 0:
						top_moves.append(str(line['pv'][0]))
				if len(top_moves) > 0:
					text += f" | Top moves: {', '.join(top_moves)}"	
			print(text)

		# Exit if we reach game count limit
		game_counter += 1
		if limit_games is not None and game_counter > limit_games:
			break
	await engine.quit()

if __name__ == "__main__":
	asyncio.run(main())