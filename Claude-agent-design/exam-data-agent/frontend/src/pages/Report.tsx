import { useMemo, useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Layout, DatePicker, Segmented, Row, Col, Spin, Button, Typography, Tag, message, Alert } from "antd";
import type { Dayjs } from "dayjs";
import { ArrowLeftOutlined, CalendarOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import MetricCard from "../components/MetricCard";
import TrendChart from "../components/TrendChart";
import InsightText from "../components/InsightText";
import { getWeeklyReport, getMonthlyReport, getRangeReport, ReportResponse, InsightParams } from "../api";
import "../styles/report.css";

const { Header, Content } = Layout;
const { Title, Text } = Typography;
const { RangePicker } = DatePicker;
const MAX_RANGE_DAYS = 180;

const METRIC_DESCRIPTIONS: Record<string, string> = {
  // 用户增长
  "本周日均注册": "本周内每天新注册用户数的平均值",
  "本周日均活跃": "本周内每天活跃用户数的平均值（至少登录一次）",
  "本周人均刷题": "本周内活跃用户的平均答题数量",
  "区间日均注册": "自定义区间内每天新注册用户数的平均值",
  "区间日均活跃": "自定义区间内每天活跃用户数的平均值",
  "区间人均刷题": "自定义区间内活跃用户的平均答题数量",
  // 用户活跃
  "注册用户": "本周期内累计新注册用户总数",
  "活跃用户": "本周期内至少登录一次的用户总数",
  "有效活跃用户": "本周期内完成至少一项核心行为（答题/模考/上课）的用户数",
  // 付费转化
  "付费用户": "本周期内完成至少一笔付费的用户总数",
  "付费转化率": "付费用户数占活跃用户数的比例",
  "复购率": "产生两次及以上付费行为的用户占付费用户数的比例",
  "ARPU": "平均每用户收入（Average Revenue Per User），总收入除以活跃用户数",
  // 用户留存
  "次日留存率": "注册次日仍然活跃的用户占比",
  "周留存率": "注册后第7天仍然活跃的用户占比",
  // 用户行为
  "答题参与率": "进行过答题行为的用户占活跃用户的比例",
  "模考参与率": "参加过模考的用户占活跃用户的比例",
  "课程参与率": "观看过课程的用户占活跃用户的比例",
  "人均播放进度": "活跃用户平均课程播放完成进度百分比",
  "人均刷题量": "活跃用户的平均答题数量",
};

/** 根据任意日期计算所在业务周(周六~周五) */
function getBusinessWeek(d: Dayjs) {
  const weekday = d.day(); // 0=Sun, 1=Mon, ..., 6=Sat
  const daysSinceSat = (weekday + 1) % 7; // Sat=0, Sun=1, Mon=2, ..., Fri=6
  const start = d.subtract(daysSinceSat, "day");
  const end = start.add(6, "day");
  return { start, end };
}

function isRangeWithinLimit(start: Dayjs, end: Dayjs) {
  return end.diff(start, "day") <= MAX_RANGE_DAYS - 1;
}

export default function Report() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [reportType, setReportType] = useState<"weekly" | "monthly">(
    (searchParams.get("type") as "weekly" | "monthly") || "weekly"
  );
  const [monthlyMode, setMonthlyMode] = useState<"month" | "range">("month");
  const [selectedDate, setSelectedDate] = useState(dayjs());
  const [month, setMonth] = useState(() => {
    const today = dayjs();
    // 每月15号前默认显示上月，15号及以后显示当月
    return today.date() < 15
      ? today.subtract(1, "month").format("YYYY-MM")
      : today.format("YYYY-MM");
  });
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(29, "day"), dayjs()]);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rangeDraft, setRangeDraft] = useState<Dayjs | null>(null);

  const businessWeek = getBusinessWeek(selectedDate);
  const weekLabel = `${businessWeek.start.format("MM/DD")} ~ ${businessWeek.end.format("MM/DD")}`;
  const isRangeMode = reportType === "monthly" && monthlyMode === "range";

  const requestParams = useMemo(() => {
    if (reportType === "weekly") {
      return {
        reportType,
        fetcher: () => getWeeklyReport(selectedDate.format("YYYY-MM-DD")),
        insightParams: { type: "weekly", date: selectedDate.format("YYYY-MM-DD") } as InsightParams,
      };
    }

    if (monthlyMode === "range") {
      return {
        reportType,
        fetcher: () => getRangeReport(range[0].format("YYYY-MM-DD"), range[1].format("YYYY-MM-DD")),
        insightParams: {
          type: "range",
          start: range[0].format("YYYY-MM-DD"),
          end: range[1].format("YYYY-MM-DD"),
        } as InsightParams,
      };
    }

    return {
      reportType,
      fetcher: () => getMonthlyReport(month),
      insightParams: { type: "monthly", date: month } as InsightParams,
    };
  }, [reportType, selectedDate, monthlyMode, month, range]);

  useEffect(() => {
    setLoading(true);
    setError("");
    requestParams.fetcher().then(setReport).catch((err: Error) => {
      setReport(null);
      setError(err.message || "报表加载失败");
    }).finally(() => setLoading(false));
  }, [requestParams]);

  const periodText = report?.period
    ? reportType === "weekly"
      ? report.period.start && report.period.end
        ? `${report.period.start} ~ ${report.period.end}`
        : ""
      : isRangeMode
        ? report.period.start && report.period.end
          ? `${report.period.start} ~ ${report.period.end}（共${report.period.weeks || 0}周）`
          : ""
        : report.period.month
          ? `${report.period.month}（共${report.period.weeks || "?"}周）`
          : ""
    : "";

  const overviewText = reportType === "weekly"
    ? `统计周期为 ${periodText || weekLabel}，重点观察典宝近期拉新、活跃、转化与留存表现。`
    : isRangeMode
      ? `统计周期为 ${periodText || `${range[0].format("YYYY-MM-DD")} ~ ${range[1].format("YYYY-MM-DD")}`}，重点复盘典宝自定义区间内的经营走势与关键波动指标。`
      : `统计周期为 ${periodText || month}，重点复盘典宝月度经营走势与关键波动指标。`;

  const emptyText = reportType === "weekly" ? "暂无周报数据" : isRangeMode ? "暂无自定义区间报告数据" : "暂无月报数据";

  const handleRangeChange = (dates: null | [Dayjs | null, Dayjs | null]) => {
    if (!dates || !dates[0] || !dates[1]) {
      return;
    }
    if (!isRangeWithinLimit(dates[0], dates[1])) {
      message.warning(`自定义日期跨度最长不能超过 ${MAX_RANGE_DAYS} 天`);
      return;
    }
    setRange([dates[0], dates[1]]);
  };

  const disabledRangeDate = (current: Dayjs) => {
    if (!rangeDraft) {
      return false;
    }
    return Math.abs(current.diff(rangeDraft, "day")) > MAX_RANGE_DAYS - 1;
  };

  const renderSection = (key: string, title: string) => {
    const section = report?.sections?.[key];
    if (!section || !section.metrics) return null;
    const metrics = Object.values(section.metrics) as any[];
    const metricKeys = Object.keys(section.metrics);
    if (!metrics.length) return null;
    const trend = section.trend || [];
    const xData = trend.map((t: any) => t.start || t.end || "");
    return (
      <section key={key} className="report-page__section">
        <div className="report-page__section-header">
          <Title level={5} className="report-page__section-title">
            {title}
          </Title>
          <div className="report-page__section-line" />
        </div>
        <div className="report-page__metrics">
          <Row gutter={[{ xs: 8, sm: 16 }, 12]}>
            {metrics.map((m: any) => (
              <Col key={m.label} xs={12} sm={12} md={8} lg={6}>
                <MetricCard data={{ ...m, description: METRIC_DESCRIPTIONS[m.label] }} />
              </Col>
            ))}
          </Row>
        </div>
        {trend.length > 1 && (
          <div className="report-page__chart">
            <TrendChart
              title={`${title}趋势`}
              xData={xData}
              series={metrics.map((m: any, idx: number) => ({
                name: m.label,
                data: trend.map((t: any) => t[metricKeys[idx]] || 0),
              }))}
            />
          </div>
        )}
      </section>
    );
  };

  return (
    <Layout className="report-page">
      <Header className="report-page__header">
        <Button className="report-page__back" icon={<ArrowLeftOutlined />} onClick={() => navigate("/")} type="text" />
        <div className="report-page__hero">
          <Title level={4} className="report-page__title">
            典宝{reportType === "weekly" ? "周" : isRangeMode ? "自定义区间" : "月"}报
          </Title>
          <Text type="secondary" className="report-page__subtitle">
            围绕用户增长、活跃、付费、留存与行为的业务复盘
          </Text>
        </div>
        <div className="report-page__controls">
          <Segmented
            value={reportType}
            options={[
              { label: "周报", value: "weekly" },
              { label: "月报", value: "monthly" },
            ]}
            onChange={(v) => setReportType(v as "weekly" | "monthly")}
          />
          {reportType === "weekly" ? (
            <DatePicker
              className="report-page__picker"
              picker="week"
              value={selectedDate}
              onChange={(d) => d && setSelectedDate(d)}
              format={`YYYY [第]ww[周]`}
            />
          ) : (
            <>
              <Segmented
                value={monthlyMode}
                className="report-page__submode"
                options={[
                  { label: "月度", value: "month" },
                  { label: "自定义区间", value: "range" },
                ]}
                onChange={(v) => setMonthlyMode(v as "month" | "range")}
              />
              {monthlyMode === "month" ? (
                <DatePicker
                  className="report-page__picker report-page__picker--month"
                  picker="month"
                  value={dayjs(month, "YYYY-MM")}
                  onChange={(d) => d && setMonth(d.format("YYYY-MM"))}
                />
              ) : (
                <RangePicker
                  className="report-page__picker report-page__picker--range"
                  value={range}
                  onCalendarChange={(dates) => setRangeDraft((dates?.[0] || dates?.[1]) ?? null)}
                  onOpenChange={(open) => {
                    if (!open) setRangeDraft(null);
                  }}
                  onChange={(dates) => handleRangeChange(dates as [Dayjs | null, Dayjs | null] | null)}
                  disabledDate={disabledRangeDate}
                  allowClear={false}
                />
              )}
            </>
          )}
          {periodText && (
            <Tag className="report-page__period-tag" icon={<CalendarOutlined />} color="blue">
              {periodText}
            </Tag>
          )}
        </div>
      </Header>

      <Content className="report-page__content">
        <div className="report-page__panel">
          {loading ? (
            <div className="report-page__state">
              <Spin size="large" />
            </div>
          ) : report ? (
            <>
              <div className="report-page__overview">
                <Title level={5} className="report-page__overview-title">
                  本期经营概览
                </Title>
                <Text className="report-page__overview-text">{overviewText}</Text>
                {isRangeMode && (
                  <div className="report-page__range-hint">自定义区间最长支持 180 天，超出范围会被拦截。</div>
                )}
              </div>
              {renderSection("user_growth", "用户增长")}
              {renderSection("active", "用户活跃")}
              {renderSection("pay", "付费转化")}
              {renderSection("retention", "用户留存")}
              {renderSection("behavior", "用户行为")}
            </>
          ) : (
            <div className="report-page__state">
              {error && <Alert className="report-page__error" type="error" showIcon message={error} />}
              <Title level={4} type="secondary">{emptyText}</Title>
            </div>
          )}
          <InsightText params={requestParams.insightParams} />
        </div>
      </Content>
    </Layout>
  );
}
