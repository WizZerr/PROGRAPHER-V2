-- Read-only modal status view. Dismiss OK before running any SDK job.
local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local home = LrPathUtils.getStandardFilePath('home')
local root = LrPathUtils.child(LrPathUtils.child(home, 'Documents'), 'ProGrapher_Research_Private')
local dir = LrPathUtils.child(LrPathUtils.child(root, 'SP_01_Catalog_Test'), 'SP_01_AUTO_LEAK_01')
local expected = LrPathUtils.child(dir, 'SP_01_AUTO_LEAK_01.lrcat')
local result = LrPathUtils.child(LrPathUtils.child(dir, 'SP_03_BRIDGE'), 'result.txt')
local function norm(p)
    return tostring(p or ''):gsub('/', '\\'):lower()
end
local current = LrApplication.activeCatalog()
local authorized = current and norm(current:getPath()) == norm(expected)
local status = 'NO JOB PREPARED'
if LrFileUtils.exists(result) == 'file' then
    local data = LrFileUtils.readFile(result)
    status = data and data:match('^status=([a-z_]+)') or 'NOT READABLE'
end
LrDialogs.message('ProGrapher SP-AUTO-03 — counterfactual research',
    'Authorized isolated research catalog: '..tostring(authorized)..
    '\nJob state: '..status..
    '\nStatus is READ ONLY. Click OK before running research.', 'info')
