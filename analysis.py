import sys
import time
import chess
import asyncio
import colorama
import argparse
from src.silicon_friend import evaluate, get_engine, get_db


argparser = argparse.ArgumentParser(
	"Analyze Lichess .pgn export",
	"Specify path to game .pgn"
)
argparser.add_argument("pgn", help="Path to pgn file")
argparser.add_argument(
	"--limit", default=0, type=int,
	help="Limit number of games to analyse")


def pretty_fen(fen):
	pretty_pieces = {
		'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟︎',
		'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙'
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


async def main(pgn_path, limit_games=None):
	pgn = open(pgn_path)
	game_counter = 1
	print_lines_to_clear = 0
	engine = await get_engine()
	db = await get_db()

	while game := chess.pgn.read_game(pgn):
		board = game.board()
		for move in game.mainline_moves():
			if print_lines_to_clear > 0:
				sys.stdout.write(f"\033[{print_lines_to_clear}A")
			board.push(move)
			start = time.time()
			evaluation = await evaluate(db, engine, board)
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
			print_lines_to_clear = 11

		# Exit if we reach game count limit
		game_counter += 1
		if limit_games is not None and game_counter > limit_games:
			break
	await engine.quit()

if __name__ == "__main__":
	args = argparser.parse_args()
	limit = args.limit if args.limit > 0 else None
	asyncio.run(main(args.pgn, limit_games=limit))