from __future__ import annotations
import chess
from typing import NamedTuple, Literal, Optional, List
from datetime import datetime
from chess.pgn import Game as LichessGame
from . import engine


COLORS = [WHITE, BLACK] = ['White', 'Black']
RESULT = [WIN, DRAW, LOSS] = ['1', '½', '0']
BIG_PIECES = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
PAWN = lambda color: chess.Piece(chess.PAWN, chess.WHITE if color == WHITE else chess.BLACK)


class GameState(NamedTuple):
	half_move_number: int
	move_number: int
	current_move: chess.Move
	next_half_move: chess.Move
	next_move: chess.Move
	current_evaluation_value: float
	current_evaluation_type: Literal['mate', 'cp']
	previous_evaluation_value: float
	previous_evaluation_type: Literal['mate', 'cp']
	absolute_centipawn_evaluation: float
	relative_centipawn_evaluation: float
	absolute_centipawn_loss: float
	relative_centipawn_loss: float
	current_evaluation: dict
	previous_evaluation: dict
	color_to_move: Literal['White', 'Black']
	is_my_move: bool
	clock_before_move: float
	clock_after_move: float
	piece_moved: chess.Piece
	is_capture: bool
	piece_captured: Optional[chess.Piece]
	is_en_passant: bool
	is_stalemate: bool
	is_checkmate: bool


class Evaluation:

	def __init__(self, game: ChessGame, state: GameState):
		self.game = game
		self.state = state
	
	def evaluate(self) -> dict:
		"""Any child must implement the evaluate method"""
		raise NotImplementedError("Child classes must implement the evaluate method")


class ChessGame:

	def __init__(self, game: LichessGame, my_name: str):
		if 'lichess' not in game.headers.get('Site', ''):
			raise ValueError("Only lichess games are supported")
		self._game = game
		self.my_name = my_name
	
	def id(self):
		return self._game.headers['Site'].split('/')[-1]
	
	def date(self):
		_string_date = self._game.headers['UTCDate'] + ' ' + self._game.headers['UTCTime']
		return datetime.strptime(_string_date, '%Y.%m.%d %H:%M:%S')

	def my_color(self):
		return WHITE if self._game.headers[WHITE] == self.my_name else BLACK
		
	def opponent_color(self):
		return BLACK if self.my_color() == WHITE else WHITE
	
	def my_rating(self):
		return int(self._game.headers[self.my_color() + 'Elo'])
	
	def opponent_rating(self):
		return int(self._game.headers[self.opponent_color() + 'Elo'])
	
	def my_rating_gain(self):
		return int(self._game.headers.get(self.my_color() + 'RatingDiff', 0))
	
	def opponent_rating_gain(self):
		return int(self._game.headers.get(self.opponent_color() + 'RatingDiff', 0))
	
	def variant(self):
		return self._game.headers['Variant']
	
	def time_control(self):
		return self._game.headers['TimeControl']

	def opening(self):
		return self._game.headers['Opening']
	
	def termination(self):
		return self._game.headers['Termination']

	def result(self):
		return self._game.headers['Result'].split('-')[0 if self.my_color() == WHITE else 1]

	def iter_game(self):
		board = self._game.board()
		previous_evaluation = engine.evaluate(board)
		moves = list(self._game.mainline_moves())
		moves_plus_half = moves[1:] + [None]
		moves_plus_one = moves[2:] + [None, None]
		color_to_move = WHITE
		for i, (move, next_half_move, next_move) in enumerate(zip(moves, moves_plus_half, moves_plus_one)):
			is_my_move = color_to_move == self.my_color()
			clock_before = self._game.clock()
			piece_moved = board.piece_at(move.from_square)
			piece_captured = board.piece_at(move.to_square)
			is_en_passant = board.is_en_passant(move)
			if is_en_passant:
				piece_captured = PAWN(WHITE) if color_to_move == WHITE else PAWN(BLACK)
			is_capture = board.is_capture(move)
			board.push(move)
			clock_after = self._game.clock()
			color_to_move = BLACK if color_to_move == WHITE else WHITE 
			current_evaluation = engine.evaluate(board)
			current_evaluation_type = current_evaluation['eval']['type']
			current_evaluation_value = current_evaluation['eval']['value'] / 100
			previous_evaluation_type = previous_evaluation['eval']['type']
			previous_evaluation_value = previous_evaluation['eval']['value'] / 100
			if current_evaluation_type != 'mate':
				absolute_centipawn_evaluation = current_evaluation_value
				relative_centipawn_evaluation = -absolute_centipawn_evaluation if color_to_move == WHITE else absolute_centipawn_evaluation
				if previous_evaluation_type == 'mate':
					absolute_centipawn_loss = None
					relative_centipawn_loss = None
				else:
					absolute_centipawn_loss = previous_evaluation_value - current_evaluation_value
					relative_centipawn_loss = absolute_centipawn_loss if color_to_move == WHITE else -absolute_centipawn_loss
			else:
				absolute_centipawn_evaluation = None
				relative_centipawn_evaluation = None
				absolute_centipawn_loss = None
				relative_centipawn_loss = None
			is_stalemate = board.is_stalemate()
			is_checkmate = current_evaluation_type == 'mate' and current_evaluation_value == 0

			yield GameState(
				half_move_number=i + 1,
				move_number=board.fullmove_number,
				current_move=move,
				next_half_move=next_half_move,
				next_move=next_move,
				current_evaluation_value=current_evaluation_value,
				current_evaluation_type=current_evaluation_type,
				previous_evaluation_value=previous_evaluation_value,
				previous_evaluation_type=previous_evaluation_type,
				absolute_centipawn_evaluation=absolute_centipawn_evaluation,
				relative_centipawn_evaluation=relative_centipawn_evaluation,
				absolute_centipawn_loss=absolute_centipawn_loss,
				relative_centipawn_loss=relative_centipawn_loss,
				current_evaluation=current_evaluation,
				previous_evaluation=previous_evaluation,
				color_to_move=color_to_move,
				is_my_move=is_my_move,
				clock_before_move=clock_before,
				clock_after_move=clock_after,
				piece_moved=piece_moved,
				is_capture=is_capture,
				piece_captured=piece_captured,
				is_en_passant=is_en_passant,
				is_stalemate=is_stalemate,
				is_checkmate=is_checkmate
			)
			previous_evaluation = current_evaluation

	def evaluate_moves(self, check_if: List[Evaluation]):
		data = []
		for state in self.iter_game():
			move_data = {
				'date': self.date(),
				'half_move_number': state.half_move_number,
				'move_number': state.move_number,
				'move': state.current_move.uci(),
				'eval': state.current_evaluation_value,
				'is_my_move': state.is_my_move
			}
			for check in check_if:
				move_data.update(check(self, state).evaluate())
			data.append(move_data)
		return data


class Mate(Evaluation):
	def evaluate(self):
		if self.state.current_evaluation_type == 'mate':
			is_missed_mate = False
			mate_in = self.state.current_evaluation_value
		elif self.state.previous_evaluation_type == 'mate' and self.state.current_evaluation_type != 'mate':
			is_missed_mate = True
			mate_in = None
		else:
			is_missed_mate = False
			mate_in = None
		return {
			'is_missed_mate': is_missed_mate,
			'mate_in': mate_in
		}


class Blunder(Evaluation):
	def evaluate(self):
		if self.state.current_evaluation_type == 'mate':
			is_blunder = False
		elif self.state.previous_evaluation_type == 'mate' and self.state.current_evaluation_type != 'mate':
			is_blunder = self.state.relative_centipawn_evaluation <= 10
		else:
			is_blunder = self.state.relative_centipawn_loss > 2
		return {
			'is_blunder': is_blunder
		}


class Mistake(Evaluation):
	def evaluate(self):
		if self.state.current_evaluation_type == 'mate':
			is_mistake = False
		elif self.state.previous_evaluation_type == 'mate' and self.state.current_evaluation_type != 'mate':
			is_mistake = (
				self.state.relative_centipawn_evaluation <= 50
				and self.state.relative_centipawn_evaluation > 10
			)
		else:
			is_mistake = (
				self.state.relative_centipawn_loss > 1
				and self.state.relative_centipawn_loss <= 2
			)
		return {
			'is_mistake': is_mistake
		}

	
class Inaccuracy(Evaluation):
	def evaluate(self):
		if self.state.current_evaluation_type == 'mate':
			is_inaccuracy = False
		elif self.state.previous_evaluation_type == 'mate' and self.state.current_evaluation_type != 'mate':
			is_inaccuracy = self.state.relative_centipawn_evaluation > 50
		else:
			is_inaccuracy = (
				self.state.relative_centipawn_loss > 0.75
				and self.state.relative_centipawn_loss <= 1
			)
		return {
			'is_inaccuracy': is_inaccuracy
		}


class TopMove(Evaluation):
	def evaluate(self):
		top_moves = [top_moves['Move'] for top_moves in self.state.previous_evaluation['top_moves']]
		if len(top_moves) > 0:
			uci = self.state.current_move.uci()
			is_top_move = top_moves[0] == uci
			is_top_three_move = uci in top_moves[:3]
			is_top_five_move = uci in top_moves[:5]
		else:
			is_top_move = False
			is_top_three_move = False
			is_top_five_move = False
		return {
			'is_top_move': is_top_move,
			'is_top_three_move': is_top_three_move,
			'is_top_five_move': is_top_five_move
		}


class OutcomeProbability(Evaluation):
	def evaluate(self):
		wdl_stats = self.state.current_evaluation['wdl_stats']
		if (self.state.is_checkmate or self.state.is_stalemate):
			win_probability = None
			draw_probability = None
			lose_probability = None
		else:
			_me_is_two = (
				   (self.state.color_to_move == BLACK and self.game.my_color() == WHITE)
				or (self.state.color_to_move == WHITE and self.game.my_color() == BLACK)
			)
			_me_stat_index = 2 if _me_is_two else 0
			_others_stat_index = 0 if _me_stat_index == 2 else 2
			win_probability = wdl_stats[_me_stat_index]
			draw_probability = wdl_stats[1]
			lose_probability = wdl_stats[_others_stat_index]
		return {
			'win_probability': win_probability,
			'draw_probability': draw_probability,
			'lose_probability': lose_probability
		}
		
			
class PieceSacrifice(Evaluation):
	def evaluate(self):
		is_moved_big_piece = self.state.piece_moved.piece_type in BIG_PIECES
		is_captured_pawn = self.state.is_capture and self.state.piece_captured.piece_type == chess.PAWN
		is_others_move_recapture = (
			self.state.next_half_move
			and self.state.next_half_move.to_square == self.state.current_move.to_square
		)
		is_next_move_recapture = (
			self.state.next_move
			and self.state.next_move.to_square == self.state.current_move.to_square
		)
		if (
			is_moved_big_piece 
			and is_captured_pawn
			and is_others_move_recapture
			and not is_next_move_recapture
		):
			is_piece_sacrifice = True
			piece_sacrificed = self.state.piece_moved.symbol()
		else:
			is_piece_sacrifice = False
			piece_sacrificed = None
		return {
			'is_piece_sacrifice': is_piece_sacrifice,
			'piece_sacrificed': piece_sacrificed
		}
