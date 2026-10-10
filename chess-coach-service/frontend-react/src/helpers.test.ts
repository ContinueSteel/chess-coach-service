import {describe,expect,it} from 'vitest'
import {groupFullMoves,initialReviewCursor,orientationFor,shouldHandleReviewKey,uciArrow} from './helpers'
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
})
