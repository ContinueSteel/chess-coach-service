import type { Analysis, Game, Settings } from './types'
import { Chess } from 'chess.js'

export type FullMove = { number:number; white?:Analysis; black?:Analysis }

export function groupFullMoves(rows:Analysis[] = []):FullMove[]{
  const grouped = new Map<number,FullMove>()
  for(const row of rows){
    const item=grouped.get(row.move_number)||{number:row.move_number}
    item[row.color]=row
    grouped.set(row.move_number,item)
  }
  return [...grouped.values()].sort((a,b)=>a.number-b.number)
}

export function initialReviewCursor(game:Game):number{
  return game.analysis_status==='complete' && (game.analysis?.length||0)>0 ? 1 : 0
}

export function orientationFor(game:Game|undefined, settings:Settings|undefined, override?:'white'|'black'):'white'|'black'{
  if(override)return override
  if(settings?.orientation_mode==='white'||settings?.orientation_mode==='black')return settings.orientation_mode
  return game?.player_color==='black'?'black':'white'
}

export function shouldHandleReviewKey(target:EventTarget|null):boolean{
  const el=target as HTMLElement|null
  if(!el)return true
  if(el.closest('[role="dialog"],[data-board-drag="true"]'))return false
  return !['INPUT','TEXTAREA','SELECT','BUTTON'].includes(el.tagName) && !el.isContentEditable
}

export function uciArrow(uci:string|undefined,color:string){
  return uci && uci.length>=4?{startSquare:uci.slice(0,2),endSquare:uci.slice(2,4),color}:null
}

export function moveResultUci(fen:string,source:string,target:string):{uci:string;fen:string}{
  const game=new Chess(fen),result=game.move({from:source,to:target,promotion:'q'})
  return {uci:`${result.from}${result.to}${result.promotion||''}`,fen:game.fen()}
}

const cueColors={best:'#e8b923',response:'#4ba3e3',continuation:'#e06b65'} as const

export function reviewPosition(cursor:number,current:Analysis|undefined,fallback:string):string{
  return cursor===0 ? fallback : current?.fen_before||fallback
}

export function engineArrowsForFen(cues:Analysis['cues']|undefined,fen:string){
  const board=new Chess(fen)
  return (cues||[]).filter(cue=>{
    if(cue.fen!==fen)return false
    try{return board.moves({verbose:true}).some(move=>`${move.from}${move.to}${move.promotion||''}`===cue.uci)}catch{return false}
  }).map(cue=>uciArrow(cue.uci,cueColors[cue.kind])).filter(Boolean)
}

export const themes={
  green:{light:'#eeeed2',dark:'#769656'},brown:{light:'#f0d9b5',dark:'#b58863'},
  blue:{light:'#dee3e6',dark:'#8ca2ad'},purple:{light:'#e7d9f2',dark:'#806a9d'}
} as const

export function pieceSetStyle(pieceSet:Settings['piece_set']):React.CSSProperties{
  return {
    classic:{fontFamily:'Georgia, serif',fontWeight:400},
    alpha:{fontFamily:'Arial Black, sans-serif',fontWeight:900},
    merida:{fontFamily:'Times New Roman, serif',fontWeight:700},
  }[pieceSet]
}
