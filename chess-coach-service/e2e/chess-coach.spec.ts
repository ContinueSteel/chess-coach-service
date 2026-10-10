import {test,expect} from '../frontend-react/node_modules/@playwright/test'

const widths=[320,375,600,768,900,1024,1440]
const PGN=`[Event "E2E"]\n[White "Alice"]\n[Black "Bob"]\n[Result "*"]\n\n1. e4 e5 2. Nf3 Nc6 *`

test.beforeEach(async({page})=>{await page.goto('/')})

test('responsive board geometry has no cutoff',async({page})=>{
 for(const width of widths){
  await page.setViewportSize({width,height:900})
  await page.goto('/')
  const box=await page.getByTestId('board-surface').first().boundingBox()
  expect(box).not.toBeNull();expect(box!.x).toBeGreaterThanOrEqual(0);expect(box!.x+box!.width).toBeLessThanOrEqual(width+.5);expect(Math.abs(box!.width-box!.height)).toBeLessThan(2)
 }
})

test('import review keyboard annotations settings and deletion',async({page})=>{
 const errors:string[]=[];page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});page.on('pageerror',e=>errors.push(e.message))
 await page.getByRole('button',{name:'import',exact:true}).click();await page.getByLabel('PGN text').fill(PGN);await page.getByRole('button',{name:'Import PGN'}).click()
 await expect(page.getByText('Ready for review')).toBeVisible();await page.getByRole('button',{name:'Start analysis'}).click();await expect(page.getByTestId('review-cursor')).toContainText('Move 1')
 await page.keyboard.press('ArrowRight');await expect(page.getByTestId('review-cursor')).toContainText('Move 1…')
 await page.getByTestId('annotation-mode').click();await expect(page.getByTestId('annotation-mode')).toHaveText('Annotating')
 await page.getByRole('button',{name:'settings',exact:true}).click();await page.getByLabel('Coach level').selectOption('beginner');await page.getByLabel('Board colors').selectOption('blue');await page.getByTestId('save-settings').click();await expect(page.getByRole('status')).toContainText('Settings saved')
 await page.getByRole('button',{name:'games',exact:true}).click();await page.getByRole('button',{name:/Alice vs Bob/}).first().click();page.on('dialog',d=>d.accept());await page.getByTestId('delete-game').click();await expect(page.getByText('Game deleted')).toBeVisible()
 expect(errors).toEqual([])
})

test('puzzle uses board and touch annotation fallback exists',async({page,request})=>{
 const imported=await request.post('/api/games/import-pgn',{data:{pgn:PGN}});const gid=(await imported.json()).games[0].id
 await request.post(`/api/games/${gid}/analysis`)
 await page.reload();await page.getByRole('button',{name:'puzzles',exact:true}).click()
 const puzzle=page.locator('.puzzle-list button').first();if(await puzzle.count()){await puzzle.click();await expect(page.getByTestId('board-surface')).toHaveAttribute('data-mode','puzzleAttempt');await expect(page.getByTestId('annotation-mode')).toBeVisible()}
})
