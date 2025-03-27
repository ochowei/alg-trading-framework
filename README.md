# Workflow 1.0
每天收盤後，重新下載歷史資料，根據回測與分析，得知隔天要進行的操作。

## Update Data:
每日下午以後使用 `uv run download_data` 來下載資料

- 使用 `uv run lookup_target` 來找出隔日進場標的
	- 在一個標的集合中找到適合進場者
- 使用最近 1000 天的資料來回測
- 並根據回測最佳年化回報率的策略，來判斷是否要進場
- WAIT [[tag/question]] 是否可以知道資金佔用的時間
- NOW [[tag/implement]] 持股時間的計算 [[roadmap/workflow-1.0]]

- 輔以人工判斷
- 目前流程: 先根據夏普值取得最佳參數，再選取其中5天內有進場訊號的

## Check Watch List:
- 使用 `uv run check_watch_list` 來確認出場標的
	- 在追蹤的標的集合中找到必須出場者
	- 使用最近 1000 天的資料來回測
	- 並根據回測最佳年化回報率的策略，來判斷是否要出場
	- 輔以人工判斷

	- TODO 實作

## Execute Order
- 根據上述的進場與出場目標在格式進行操作