import {describe,expect,it} from 'vitest'
import {engineArrowsForFen,groupFullMoves,initialReviewCursor,moveResultUci,orientationFor,pieceSetStyle,reviewPosition,shouldHandleReviewKey,uciArrow} from './helpers'
import type {Analysis,Game,Settings} from './types'

const row=(ply:number,color:'white'|'black',move_number:number):Analysis=>({ply,color,move_number,san:'e4',fen_before:'',fen_after:'',eval_cp:0,loss_cp:0,classification:'best',best_move_uci:'e2e4',best_move_san:'e4',pv:[],coach:''})
const game={analysis_status:'complete',analysis:[row(1,'white',1),row(2,'black',1)],player_color:'black'} as Game
const settings={orientation_mode:'player'} as Settings

describe('review helpers',()=>{
 it('groups white and black plies into full moves',()=>expect(groupFullMoves(game.analysis)).toEqual([{number:1,white:game.analysis![0],black:game.analysis![1]}]))
 it('starts completed review at move one white ply',()=>expect(initialReviewCursor(game)).toBe(1))
 it('puts player color at bottom and honors override',()=>{expect(orientationFor(game,settings)).toBe('black');expect(orientationFor(game,settings,'white')).toBe('white')})
 it('ignores keyboard navigation in form controls',()=>{const input=document.createElement('input');expect(shouldHandleReviewKey(input)).toBe(false);expect(shouldHandleReviewKey(document.body)).toBe(true)})
 it('turns legal UCI-shaped strings into arrows',()=>expect(uciArrow('e2e4','#fff')).toEqual({startSquare:'e2',endSquare:'e4',color:'#fff'}))
 it('shows the pre-move position and only arrows legal on that exact FEN',()=>{
  const before='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
  const after='rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'
  const selected={...row(1,'white',1),fen_before:before,fen_after:after,cues:[
   {kind:'best',label:'Best',uci:'e2e4',san:'e4',fen:before},
   {kind:'response',label:'Expected reply',uci:'e7e5',san:'e5',fen:after},
   {kind:'continuation',label:'Continuation',uci:'g1f3',san:'Nf3',fen:'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2'},
   {kind:'response',label:'Expected reply',uci:'e7e5',san:'e5',fen:before},
  ]} as Analysis
  expect(reviewPosition(1,selected,before)).toBe(before)
  expect(engineArrowsForFen(selected.cues,before)).toEqual([{startSquare:'e2',endSquare:'e4',color:'#e8b923'}])
 })
 it('returns the actual promotion UCI suffix from chess.js',()=>expect(moveResultUci('8/P7/8/8/8/8/7k/5K2 w - - 0 1','a7','a8').uci).toBe('a7a8q'))
 it('maps each piece-set preference to a distinct local style',()=>expect(new Set(['classic','alpha','merida'].map(x=>pieceSetStyle(x as Settings['piece_set']).fontFamily)).size).toBe(3))
})
