import chess
import asyncio
import argparse
import pandas as pd
from src import core

HELLO = r"""
       _       _     __  __                       
      /_\   __| |__ |  \/  |__ _ __ _ _ _ _  _ ___
     / _ \ (_-< / / | |\/| / _` / _` | ' \ || (_-<
    /_/ \_\/__/_\_\ |_|  |_\__,_\__, |_||_\_,_/__/
                                |___/             
"""

argparser = argparse.ArgumentParser(
	"Ask Magnus: 'Yo bro, how`s my chess?'",
	"Specify path to game .pgn"
)
argparser.add_argument("pgn", help="Path to pgn file")
argparser.add_argument("username", help="Your lichess username")
argparser.add_argument(
	"--limit", default=0, type=int,
	help="Limit number of games to analyse")


async def main(pgn_path, username, limit_games=None):
    pgn = open(pgn_path)
    game_counter = 1

    data = []
    while chess_game := chess.pgn.read_game(pgn):
        game = core.ChessGame(chess_game, username)
        data += await game.evaluate_moves([
            core.Mate])
            #core.Blunder, 
            #core.Mistake,
            #core.Inaccuracy,
            #core.TopMove,
            #core.OutcomeProbability,
            #core.PieceSacrifice])
        game_counter += 1
        if limit_games is not None and game_counter > limit_games:
            break
    df = pd.DataFrame(data)
    breakpoint()


if __name__ == "__main__":
    print(HELLO)
    args = argparser.parse_args()
    limit = args.limit if args.limit > 0 else None
    asyncio.run(main(args.pgn, args.username, limit_games=limit))