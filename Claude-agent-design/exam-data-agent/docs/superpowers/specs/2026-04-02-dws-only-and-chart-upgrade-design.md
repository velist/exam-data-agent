# 设计文档：仅使用 dws 数据源 + 对话页图表升级

> 日期：2026-04-02 | 状态：待实施

---

## 背景

典宝数据助手当前白名单含 10 张表：6 张 `dws.*`（清洗后的数仓表）和 4 张 `bigdata.*`（原始业务库视图）。为简化数据治理、降低维护成本，决定仅保留 `dws` 库作为唯一数据源。

同时，对话页的图表使用纯 Canvas 手绘（`SimpleChart`），功能受限（无 tooltip、无 legend、单系列），需升级为与报表页一致的 ECharts 交互式图表，并增加表格 XLSX 下载功能。

---

## 任务一：移除 bigdata 数据源

### 目标

- 从白名单中移除 `bigdata.*` 的 4 张表
- 清理 NL2SQL 提示词中的 bigdata 表结构描述和 SQL 示例
- 当用户问到销售/画像类问题时，引导 LLM 用 dws 表近似回答

### 涉及文件

| 文件 | 变更内容 |
|------|----------|
| `backend/config.py` | 从 `ALLOWED_TABLES` 列表中删除 `bigdata.v_ws_salesflow_ex`、`bigdata.v_ksb_users_ex`、`bigdata.v_ws_vnsalesrank`、`bigdata.v_ksb_userclick` |
| `backend/prompts/nl2sql.txt` | 1. 删除 bigdata 表结构描述区块（约 50 行）<br>2. 删除引用 bigdata 表的 8+ 个 SQL 示例块<br>3. 修改意图分类：移除"销售收入/业绩统计/用户画像/埋点行为"独立类别，将可覆盖的需求映射到 dws 表<br>4. 在提示词中新增引导规则（见下方"引导规则实施方式"） |
| `backend/services/chat.py` | 第 251 行 SQL 修复重试提示词中硬编码了 bigdata 表名，需改为仅引用 dws 库 |
| `backend/tests/test_sql_validator.py` | `test_allow_bigdata_sales` 测试用例需改为验证 bigdata 表被**拦截** |
| `backend/sql_validator.py` | 无需改动 — bigdata 表不在白名单中自然被拦截；`_is_table_allowed` 中 `dws.` 开头的宽松放行逻辑保持不变 |

### 引导规则实施方式

通过 `nl2sql.txt` 提示词指令实现，**不在 chat.py 中新增代码逻辑**：

- 在提示词中明确告知 LLM：当前系统仅支持 dws 库中的数据表
- 当用户问到销售明细、用户画像、点击埋点等原 bigdata 覆盖的领域时，LLM 应：
  1. 优先尝试用 dws 表中的近似数据回答（如用付费转化表回答销售相关问题）
  2. 如果确实无法用 dws 表回答，直接在 SQL 输出位置返回特殊标记 `-- NO_DATA_AVAILABLE`，后跟一句自然语言说明
- `chat.py` 中 `_clean_sql_response` 已有对非 SQL 输出的处理逻辑，检测到该标记时跳过 SQL 执行，直接将说明文本作为回复返回

### dws 表对 bigdata 需求的覆盖映射

| 原 bigdata 需求 | dws 近似覆盖 | 降级说明 |
|-----------------|-------------|----------|
| 销售流水（`v_ws_salesflow_ex`） | `dws_pay_user_report_week`（付费转化、ARPU、复购率） | 无日粒度明细和单笔金额，只能给出周维度付费汇总 |
| 用户画像（`v_ksb_users_ex`） | `dws_user_daily_quiz_stats_day` + `dws_active_user_report_week` | 无渠道、省份、职称等画像维度，仅有注册/活跃统计 |
| 销售排名（`v_ws_vnsalesrank`） | `dws_pay_user_report_week`（付费维度汇总） | 无部门维度排名 |
| 点击行为（`v_ksb_userclick`） | `dws_user_behavior_report_week`（参与率） | 无页面/按钮级埋点明细 |

### 不受影响的部分

- 报表页 SQL 模板（`sql_templates/`）：全部使用 dws 表，无需改动
- 报表缓存（`report_cache.py`、`query_cache.py`）：无需改动
- 前端代码：无需改动

---

## 任务二：对话页图表升级 + XLSX 下载

### 目标

- 对话气泡中的图表从 Canvas 手绘升级为 ECharts，与报表页视觉一致
- 支持多系列数据展示（表格中的所有数值列）
- 添加表格 XLSX 下载按钮

### 新组件：`ChatChart.tsx`

**技术选型**：`echarts-for-react`（已有依赖，报表页在用）

**Props 接口**：
```typescript
interface ChatChartProps {
  type: "line" | "bar";
  labels: string[];
  series: { name: string; data: number[] }[];
}
```

**ECharts 配置**（继承 TrendChart 风格）：
- 调色板：`["#00b4d8", "#66ffd1", "#0284c7", "#38bdf8", "#0f766e"]`
- Tooltip：`trigger: "axis"`，深色背景 `rgba(15,23,42,0.88)`，白色文字，`appendToBody: true`
- Legend：底部圆形图标，单系列时隐藏
- Grid：`left: 3%, right: 4%, top: 16px, bottom: 18%`，`containLabel: true`
- X 轴：类目轴，标签旋转 30 度
- 系列：`smooth: true`，`symbolSize: 8`，`lineWidth: 3`；第一系列有面积填充
- 柱状图：`boundaryGap: true`，圆角柱子（`borderRadius: [4,4,0,0]`）
- 高度：240px（比报表页 300px 更紧凑，适配气泡场景）
- 无 Card 包裹（区别于 TrendChart）

### ChatBubble 改造

**`extractChartData` 函数升级**：
- 当前：只提取第一个数值列 → `data: number[]`
- 升级：提取所有数值列 → `series: { name: string; data: number[] }[]`
- 每个数值列的 `name` 取自表头列名

**图表类型判断**（保持现有逻辑）：
- labels 含日期格式（`\d{4}[-/]\d{2}`）→ 折线图
- 否则 → 柱状图

**渲染顺序**：
1. 数据表格（Ant Design Table）
2. 下载按钮（右对齐，表格和图表之间）
3. 图表（`ChatChart`）
4. 洞察文本

### XLSX 下载

**依赖**：`xlsx`（SheetJS）— 需 `npm install xlsx`

**实现**：
- 纯前端客户端导出，无需后端参与
- 从 `table.columns` + `table.rows` 构建 worksheet
- 文件名：`典宝数据_YYYY-MM-DD_HH-mm.xlsx`

**按钮样式**：
- 图标 + 文字「下载 XLSX」
- 配色与主题一致：`rgba(0,180,216,0.12)` 背景、`#00b4d8` 文字/边框
- 圆角 8px，hover 加深

### 清理

- 确认 `SimpleChart.tsx` 无其他引用后删除
- 无需改动 `TrendChart.tsx`（报表页继续使用）

---

## 测试计划

### 任务一
- [ ] 验证 `ALLOWED_TABLES` 只包含 dws 表
- [ ] 验证查询 bigdata 表的 SQL 被 validator 拦截
- [ ] 验证 `chat.py` 中 SQL 修复提示词不再引用 bigdata 表
- [ ] 更新 `test_sql_validator.py` 中 bigdata 相关用例为拦截断言
- [ ] 验证用户问"销售流水"时 LLM 能用 dws 表近似回答
- [ ] 验证用户问无法覆盖的问题时返回合理说明
- [ ] 运行全部后端测试确保无回归

### 任务二
- [ ] 对话页单系列数据显示折线图/柱状图正确
- [ ] 对话页多系列数据显示多条线且 legend 可交互
- [ ] Tooltip 悬停显示所有系列数值
- [ ] 单系列时 legend 自动隐藏
- [ ] 下载按钮生成正确的 XLSX 文件
- [ ] XLSX 包含完整表头和数据（含中文列名）
- [ ] 空表格时下载按钮不显示
- [ ] 移动端图表和按钮响应式正常
- [ ] 大量类目（50+ 行数据）时图表渲染正常、标签不重叠
- [ ] 运行全部前端测试确保无回归
