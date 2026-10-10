import type {PieceRenderObject} from 'react-chessboard'

type Style='classic'|'alpha'|'merida'
type Kind='P'|'N'|'B'|'R'|'Q'|'K'

const silhouettes:Record<Style,Record<Kind,string>>={
 classic:{
  P:'M22 11a6 6 0 1 1 12 0 6 6 0 0 1-12 0Zm2 8h8l2 16H22l2-16Zm-5 17h18l3 8H16l3-8Z',
  N:'M18 42h23l-3-7H25c1-8 8-11 13-15l-3-12-8 3-5-5-2 13 7-3c-7 5-12 12-9 26Z',
  B:'M25 8l7 7-4 4c5 3 7 8 6 14H22c-1-6 1-11 6-14l-4-4 1-7Zm-5 26h16l5 10H15l5-10Z',
  R:'M17 7h6v6h5V7h5v6h6V7h5v13l-5 4 2 13 4 7H11l4-7 2-13-5-4V7h5Z',
  Q:'M12 13a4 4 0 1 1 6 3l6 9 4-12a4 4 0 1 1 6 0l4 12 6-9a4 4 0 1 1 4 4l-5 17 5 7H12l5-7-5-17a4 4 0 1 1 0-7Z',
  K:'M25 5h6v7h7v6h-7v7c6 2 9 7 8 13l5 6H12l5-6c-1-6 2-11 8-13v-7h-7v-6h7V5Z',
 },
 alpha:{
  P:'M28 5 36 13 32 21 38 39 45 45H11l7-6 6-18-4-8 8-8Z',
  N:'M12 45h35l-8-9H28l15-13-6-17-13 4-9-5 2 17 10-4C17 28 12 34 12 45Z',
  B:'M28 4 38 16l-7 7 8 16 6 6H11l6-6 8-16-7-7L28 4Z',
  R:'M10 5h10v8h5V5h6v8h5V5h10v18l-7 5 4 11 5 6H8l5-6 4-11-7-5V5Z',
  Q:'M7 8l11 9L28 4l10 13L49 8l-7 31 6 6H8l6-6L7 8Z',
  K:'M24 3h8v8h9v8h-9v7l10 13 6 6H8l6-6 10-13v-7h-9v-8h9V3Z',
 },
 merida:{
  P:'M28 6c7 0 10 8 5 13 5 6 3 11 1 15h6l4 10H12l4-10h6c-2-4-4-9 1-15-5-5-2-13 5-13Z',
  N:'M15 44h29l-5-7H24c0-7 8-9 15-16l-4-13-9 5-8-3 3 11 8-4c-5 7-17 10-14 27Z',
  B:'M28 5c7 6 8 11 3 17 8 6 5 12 3 15h5l5 7H12l5-7h5c-2-3-5-9 3-15-5-6-4-11 3-17Z',
  R:'M13 6h8v7h5V6h4v7h5V6h8v14l-6 5 2 12h4l4 7H9l4-7h4l2-12-6-5V6Z',
  Q:'M10 12c0-5 7-5 7 0 0 2-1 3-2 4l9 10 4-13c-5-3-1-10 3-6 2 2 1 5-1 6l4 13 9-10c-5-4 1-10 4-5 2 3-1 6-3 6l-5 20h3l5 7H9l5-7h3l-5-20c-2 0-3-3-2-5Z',
  K:'M26 4h4v8h8v4h-8v8c7 3 10 8 7 13h4l6 7H9l6-7h4c-3-5 0-10 7-13v-8h-8v-4h8V4Z',
 }
}

function renderPiece(style:Style,code:string,svgStyle?:React.CSSProperties){
 const black=code[0]==='b',kind=code[1] as Kind
 const fill=black?'#232725':'#f8f7f0',stroke=black?'#050706':'#343834'
 return <svg data-piece={code} data-piece-style={style} viewBox="0 0 56 52" xmlns="http://www.w3.org/2000/svg" style={{width:'100%',height:'100%',...svgStyle}} aria-hidden="true">
  <path d={silhouettes[style][kind]} fill={fill} stroke={stroke} strokeWidth={style==='alpha'?2.2:1.7} strokeLinejoin={style==='alpha'?'miter':'round'}/>
  {style==='classic'&&<path d="M17 39h22" fill="none" stroke={stroke} strokeWidth="1.4"/>}
  {style==='merida'&&<path d="M15 41h26" fill="none" stroke={stroke} strokeWidth="1.2"/>}
 </svg>
}

const codes=['wP','wN','wB','wR','wQ','wK','bP','bN','bB','bR','bQ','bK']
const makeSet=(style:Style):PieceRenderObject=>Object.fromEntries(codes.map(code=>[code,(props?:{svgStyle?:React.CSSProperties})=>renderPiece(style,code,props?.svgStyle)]))

export const pieceSets={classic:makeSet('classic'),alpha:makeSet('alpha'),merida:makeSet('merida')}
