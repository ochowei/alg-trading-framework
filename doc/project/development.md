## Workflows

### 策略開發
#### 流程
1. 修改 src/ 裡面內容
2. 利用指令進行回測
3. 撰寫開發日誌
4. git 歸檔


### Framework 更動
#### 流程
1. 修改 src/ 裡面內容或者相關程式碼
2. 確認 README.md 是否需要調整
3. 進行單元測試
4. 撰寫開發日誌
5. git 歸檔


### 更改專案文件
1. 更改 doc/project 裡面的內容
2. git 歸檔


### 監控標的
1. 使用 `uv run download_data` 下載所有監控標的的最新資料
2. 確認標的列表是否為最新（依照需求調整）
3. 執行 `uv run check_target` 檢查標的是否符合出場條件，並產生回測紀錄（存放於 `log/` 資料夾中）
4. 儲存與整理監控結果（建議放入 `monitor_results/YYYY-MM-DD.md`）
5. git 歸檔
 

### 思考
1. 在 `journal/` 記錄當日靈感、反思或疑問（可用 `tags:` 標記）
2. 將重要靈感移入 `ideas/` 或 `goals/` 做為後續發展種子
3. 若形成具體任務，建立一筆 workflow 任務（放入 `workflow_runs/` 中）
4. 可於 `notes/` 撰寫延伸技術或概念筆記
5. git 歸檔
---

## 好用Prompt
> 我想要 XXX, 請幫我確認如何利用 development.md 的 workflow 來完成?
> 我想要 XXX, 請幫我建立 workflow 的文件，並附上檔名
> 這是目前的專案，請幫助我在 development.md 裡面建立 XXX 的 workflow