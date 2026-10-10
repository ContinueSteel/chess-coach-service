import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {pieceSets} from './pieces'

const pieceCodes=['wP','wN','wB','wR','wQ','wK','bP','bN','bB','bR','bQ','bK']

describe('local piece renderers',()=>{
 it('renders every piece type with distinct SVG geometry for every style',()=>{
  for(const code of pieceCodes){
   const markup=['classic','alpha','merida'].map(style=>renderToStaticMarkup(pieceSets[style as keyof typeof pieceSets][code]()))
   expect(markup.every(svg=>svg.startsWith('<svg')&&svg.includes(`data-piece="${code}"`))).toBe(true)
   expect(new Set(markup).size).toBe(3)
  }
 })
})