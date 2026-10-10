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
 await expect(page.getByText('Ready for review')).toBeVisible();await page.getByRole('button',{name:'Start analysis'}).click();await expect(page.getByTestId('review-cursor')).toContainText('Move 1',{timeout:30000})
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

test('all analysis settings are editable and persist after reload',async({page,request})=>{
 await page.getByRole('button',{name:'settings',exact:true}).click()
 const values={
  'Chess.com username':'roundtrip_user',
  'Analysis time (ms)':'375',
  'Inaccuracy threshold (cp)':'61',
  'Mistake threshold (cp)':'123',
  'Blunder threshold (cp)':'246',
  'Puzzle threshold (cp)':'177',
 }
 for(const [label,value] of Object.entries(values))await page.getByLabel(label).fill(value)
 await page.getByTestId('save-settings').click();await expect(page.getByRole('status')).toContainText('Settings saved')
 await page.reload();await page.getByRole('button',{name:'settings',exact:true}).click()
 for(const [label,value] of Object.entries(values))await expect(page.getByLabel(label)).toHaveValue(value)
 const saved=await (await request.get('/api/settings')).json()
 expect(saved).toMatchObject({chesscom_username:'roundtrip_user',analysis_time_ms:375,inaccuracy_threshold:61,mistake_threshold:123,blunder_threshold:246,puzzle_threshold:177})
})

test('promotion drag sends the five-character UCI to puzzle API',async({page})=>{
 await page.route('**/api/puzzles',route=>route.fulfill({json:{items:[{id:991,game_id:0,move_ply:1,fen:'8/P7/8/8/8/8/7k/5K2 w - - 0 1',attempts:0,solved:0}]}}))
 let submitted=''
 await page.route('**/api/puzzles/991/attempt',async route=>{submitted=(await route.request().postDataJSON()).move;await route.fulfill({json:{correct:true,solution:'a8=Q'}})})
 await page.reload();await page.getByRole('button',{name:'puzzles',exact:true}).click();await page.getByRole('button',{name:/Position #991/}).click()
 const from=page.locator('[data-square="a7"]'),to=page.locator('[data-square="a8"]'),a=await from.boundingBox(),b=await to.boundingBox()
 expect(a).not.toBeNull();expect(b).not.toBeNull();await page.mouse.move(a!.x+a!.width/2,a!.y+a!.height/2);await page.mouse.down();await page.mouse.move(b!.x+b!.width/2,b!.y+b!.height/2,{steps:12});await page.mouse.up();await expect.poll(()=>submitted).toBe('a7a8q')
})

test('promotion drag sends the five-character UCI to trial API',async({page})=>{
 const game={id:992,white:'Promoter',black:'King',result:'*',played_at:'',source:'fixture',analysis_status:'complete',ply_count:1,player_color:'white',analysis:[{ply:1,move_number:1,color:'white',san:'a8=Q',fen_before:'8/P7/8/8/8/8/7k/5K2 w - - 0 1',fen_after:'Q7/8/8/8/8/8/7k/5K2 b - - 0 1',eval_cp:0,loss_cp:0,classification:'best',best_move_uci:'a7a8q',best_move_san:'a8=Q',pv:[],cues:[],coach:'Promote.'}]}
 await page.route('**/api/games/992',route=>route.fulfill({json:game}));await page.route('**/api/games',route=>route.fulfill({json:{items:[game],total:1}}))
 let submitted='';await page.route('**/api/positions/evaluate-trial',async route=>{submitted=(await route.request().postDataJSON()).move;await route.fulfill({json:{move_uci:submitted,move_san:'a8=Q',fen_after:game.analysis[0].fen_after,loss_cp:0,classification:'best',best_move_san:'a8=Q',feedback:'Promoted.',cues:[]}})})
 await page.reload();await page.getByRole('button',{name:'games',exact:true}).click();await page.getByRole('button',{name:/Promoter vs King/}).click()
 const from=page.locator('[data-square="a7"]'),to=page.locator('[data-square="a8"]'),a=await from.boundingBox(),b=await to.boundingBox();expect(a).not.toBeNull();expect(b).not.toBeNull()
 await page.mouse.move(a!.x+a!.width/2,a!.y+a!.height/2);await page.mouse.down();await page.mouse.move(b!.x+b!.width/2,b!.y+b!.height/2,{steps:12});await page.mouse.up();await expect.poll(()=>submitted).toBe('a7a8q')
})

test('trainer reset restores the source square after a move',async({page})=>{
 await page.getByRole('button',{name:'trainer',exact:true}).click()
 const from=page.locator('[data-square="e2"]'),to=page.locator('[data-square="e4"]')
 const a=await from.boundingBox(),b=await to.boundingBox();expect(a).not.toBeNull();expect(b).not.toBeNull()
 await page.mouse.move(a!.x+a!.width/2,a!.y+a!.height/2);await page.mouse.down();await page.mouse.move(b!.x+b!.width/2,b!.y+b!.height/2,{steps:12});await page.mouse.up()
 await expect(to.locator('div[data-piece="wP"]')).toBeVisible()
 await page.getByRole('button',{name:'Reset',exact:true}).click()
 await expect(from.locator('div[data-piece="wP"]')).toBeVisible()
 await expect(to.locator('div[data-piece="wP"]')).toHaveCount(0)
})
