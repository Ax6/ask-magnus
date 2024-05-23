import chess
import redis
from src.engine import evaluate, ENGINE_OPTIONS
from stockfish import Stockfish
from datetime import datetime

BIG_PIECES = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]

engine = Stockfish(**ENGINE_OPTIONS)
db = redis.Redis()

def extract_game_features(game):
	data = []
	"""
	Features per move:
	- game_id
	- game_date
	- my_color
	- opponent_color
	- my_rating
	- opponent_rating
	- my_rating_gain
	- opponent_rating_gain
	- variant
	- time_control
	- opening
	- termination
	- result
	- my_time
	- opponent_time
	- half_move_number
	- move_number
	- move
	- is_my_move
	- is_best_move
	- is_top_three_move
	- is_top_five_move
	- is_capture
	- is_piece_sacrifice
	- is_inaccuracy
	- is_mistake
	- is_blunder
	- is_missed_mate
	- piece_sacrificed
	- absolute_centipawn_evaluation
	- relative_centipawn_evaluation
	- absolute_centipawn_loss
	- relative_centipawn_loss
	- mate_in
	- board
	"""
	game_id = game.headers['Site'].split('/')[-1]
	game_date = datetime.strptime(game.headers['UTCDate'] + ' ' + game.headers['UTCTime'], '%Y.%m.%d %H:%M:%S')
	my_color = 'White' if game.headers['White'] == 'Ax_6' else 'Black'
	opponent_color = 'Black' if my_color == 'White' else 'White'
	my_rating = int(game.headers[my_color + 'Elo'])
	opponent_rating = int(game.headers[opponent_color + 'Elo'])
	my_rating_gain = int(game.headers.get(my_color + 'RatingDiff', 0))
	opponent_rating_gain = int(game.headers.get(opponent_color + 'RatingDiff', 0))
	variant = game.headers['Variant']
	time_control = game.headers['TimeControl']
	opening = game.headers['Opening']
	termination = game.headers['Termination']
	result = game.headers['Result'].split('-')[0 if my_color == 'White' else 1]

	board = game.board()
	previous_evaluation = evaluate(db, engine, board)
	moves = list(game.mainline_moves())
	color_to_move = 'White'
	for i, (move, others_move, next_move) in enumerate(zip(moves, moves[1:] + [None], moves[2:] + [None, None])):
		is_my_move = color_to_move == my_color
		clock_before = game.clock()
		piece_moved = board.piece_at(move.from_square)
		piece_captured = board.piece_at(move.to_square)
		if board.is_en_passant(move):
			piece_captured = chess.Piece(chess.PAWN, chess.WHITE) if color_to_move == 'White' else chess.Piece(chess.PAWN, chess.BLACK)
		is_capture = board.is_capture(move)

		board.push(move)

		clock_after = game.clock()
		color_to_move = 'Black' if color_to_move == 'White' else 'White'
		
		evaluation = evaluate(db, engine, board)

		my_time = clock_after if is_my_move else clock_before
		opponent_time = clock_after if not is_my_move else clock_before
		move_number = board.fullmove_number

		top_moves = [top_moves['Move'] for top_moves in previous_evaluation['top_moves']]
		if len(top_moves) > 0:
			is_best_move = top_moves[0] == move.uci()
			is_top_three_move = move.uci() in top_moves[:3]
			is_top_five_move = move.uci() in top_moves[:5]
		else:
			raise Exception('Unexpected situation')
		
		moved_big_piece = piece_moved.piece_type in BIG_PIECES
		captured_pawn = is_capture and piece_captured.piece_type == chess.PAWN
		others_move_recapture = others_move and others_move.to_square == move.to_square
		next_move_recapture = next_move and next_move.to_square == move.to_square
		if moved_big_piece and captured_pawn and others_move_recapture and not next_move_recapture:
			is_piece_sacrifice = True
			piece_sacrificed = piece_moved.symbol()
		else:
			is_piece_sacrifice = False
			piece_sacrificed = None
		
		previous_evaluation_type = previous_evaluation['eval']['type']
		previous_evaluation_value = previous_evaluation['eval']['value']
		current_evaluation_value = evaluation['eval']['value']
		current_evaluation_type = evaluation['eval']['type']

		if current_evaluation_type != 'mate':
			absolute_centipawn_evaluation = current_evaluation_value / 100
			relative_centipawn_evaluation = -absolute_centipawn_evaluation if color_to_move == 'White' else absolute_centipawn_evaluation
		else:
			absolute_centipawn_evaluation = None
			relative_centipawn_evaluation = None

		if current_evaluation_type == 'mate':
			is_missed_mate = False
			mate_in = current_evaluation_value
			absolute_centipawn_loss = None
			relative_centipawn_loss = None
			is_inaccuracy = False
			is_mistake = False
			is_blunder = False
		elif previous_evaluation_type == 'mate' and current_evaluation_type != 'mate':
			is_missed_mate = True
			mate_in = None
			absolute_centipawn_loss = None
			relative_centipawn_loss = None
			is_inaccuracy = relative_centipawn_evaluation > 50
			is_mistake = relative_centipawn_evaluation > 10 and relative_centipawn_evaluation <= 50
			is_blunder = relative_centipawn_evaluation <= 10
		else:
			is_missed_mate = False
			mate_in = None
			absolute_centipawn_loss = (current_evaluation_value - previous_evaluation_value) / 100
			relative_centipawn_loss = -absolute_centipawn_loss if color_to_move == 'White' else absolute_centipawn_loss
			is_inaccuracy = relative_centipawn_loss < -0.75 and relative_centipawn_loss >= -1
			is_mistake = relative_centipawn_loss < -1 and relative_centipawn_loss >= -2
			is_blunder = relative_centipawn_loss < -2

		if (current_evaluation_type == 'mate' and current_evaluation_value == 0) or board.is_stalemate():
			win_probability = None
			draw_probability = None
			lose_probability = None
		else:
			_me_stat_index = 0 if my_color == 'White' else 2
			_others_stat_index = 0 if _me_stat_index == 2 else 2
			try:
				win_probability = evaluation['wdl_stats'][_me_stat_index]
			except:
				breakpoint()
			draw_probability = evaluation['wdl_stats'][1]
			lose_probability = evaluation['wdl_stats'][_others_stat_index]

		data.append({
			'game_id': game_id,
			'game_date': game_date,
			'my_color': my_color,
			'opponent_color': opponent_color,
			'my_rating': my_rating,
			'opponent_rating': opponent_rating,
			'my_rating_gain': my_rating_gain,
			'opponent_rating_gain': opponent_rating_gain,
			'variant': variant,
			'time_control': time_control,
			'opening': opening,
			'termination': termination,
			'result': result,
			'my_time': my_time,
			'opponent_time': opponent_time,
			'half_move_number': i + 1,
			'move_number': move_number,
			'move': move.uci(),
			'is_my_move': is_my_move,
			'is_best_move': is_best_move,
			'is_top_three_move': is_top_three_move,
			'is_top_five_move': is_top_five_move,
			'is_capture': is_capture,
			'is_piece_sacrifice': is_piece_sacrifice,
			'is_inaccuracy': is_inaccuracy,
			'is_mistake': is_mistake,
			'is_blunder': is_blunder,
			'is_missed_mate': is_missed_mate,
			'piece_sacrificed': piece_sacrificed,
			'absolute_centipawn_evaluation': absolute_centipawn_evaluation,
			'relatice_centipawn_evaluation': relative_centipawn_evaluation,
			'absolute_centipawn_loss': absolute_centipawn_loss,
			'relative_centipawn_loss': relative_centipawn_loss,
			'mate_in': mate_in,
			'win_probability': win_probability,
			'draw_probability': draw_probability,
			'lose_probability': lose_probability,
			'board': board.copy()
		})
		previous_evaluation = evaluation
	return data