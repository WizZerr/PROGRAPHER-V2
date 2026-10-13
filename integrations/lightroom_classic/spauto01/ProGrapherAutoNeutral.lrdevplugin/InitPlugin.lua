-- Start the research bridge watcher when the plug-in is enabled.
-- Only a prepared local job in the exact disposable catalog is processed.
local worker = require 'AutoWorker'
worker.start()
