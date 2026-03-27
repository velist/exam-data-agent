import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Layout, DatePicker, Segmented, Row, Col, Spin, Button, Typography, Divider, Tag } from "antd";
import { ArrowLeftOutlined, CalendarOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import MetricCard from "../components/MetricCard";
import TrendChart from "../components/TrendChart";
import InsightText from "../components/InsightText";
import { getWeeklyReport, getMonthlyReport, ReportResponse } from "../api";

const { Header, Content } = Layout;
const { Title, Text } = Typography;

/** 根据任意日期计算所在业务周(周六~周五) */
function getBusinessWeek(d: dayjs.Dayjs) {
  const weekday = d.day(); // 0=Sun, 1=Mon, ..., 6=Sat
  const daysSinceSat = (weekday + 1) % 7; // Sat=0, Sun=1, Mon=2, ..., Fri=6
  const start = d.subtract(daysSinceSat, "day");
  const end = start.add(6, "day");
  return { start, end };
}

export default function Report() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [reportType, setReportType] = useState<"weekly" | "monthly">(
    (searchParams.get("type") as "weekly" | "monthly") || "weekly"
  );
  const [selectedDate, setSelectedDate] = useState(dayjs());
  const [month, setMonth] = useState(dayjs().format("YYYY-MM"));
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);

  // 计算当前选中的业务周区间
  const businessWeek = getBusinessWeek(selectedDate);
  const weekLabel = `${businessWeek.start.format("MM/DD")} ~ ${businessWeek.end.format("MM/DD")}`;
  const dateParam = reportType === "weekly" ? selectedDate.format("YYYY-MM-DD") : month;

  useEffect(() => {
    setLoading(true);
    const fetch = reportType === "weekly"
      ? getWeeklyReport(selectedDate.format("YYYY-MM-DD"))
      : getMonthlyReport(month);
    fetch.then(setReport).catch(() => setReport(null)).finally(() => setLoading(false));
  }, [reportType, selectedDate, month]);

  // 报告标题区间文字
  const periodText = report?.period
    ? reportType === "weekly"
      ? `${report.period.start} ~ ${report.period.end}`
      : `${report.period.month}（共${(report.period as any).weeks || "?"}周）`
    : "";

  const renderSection = (key: string, title: string) => {
    const section = report?.sections?.[key];
    if (!section || !section.metrics) return null;
    const metrics = Object.values(section.metrics) as any[];
    const metricKeys = Object.keys(section.metrics);
    const trend = section.trend || [];
    const xData = trend.map((t: any) => t.start || t.end || "");
    return (
      <div key={key} style={{ marginBottom: 32 }}>
        <Title level={5}>{title}</Title>
        <Row gutter={[16, 16]}>
          {metrics.map((m: any) => (
            <Col key={m.label} xs={12} sm={8} md={6}>
              <MetricCard data={m} />
            </Col>
          ))}
        </Row>
        {trend.length > 1 && (
          <TrendChart
            title={`${title}趋势`}
            xData={xData}
            series={metrics.map((m: any, idx: number) => ({
              name: m.label,
              data: trend.map((t: any) => t[metricKeys[idx]] || 0),
            }))}
          />
        )}
        <Divider />
      </div>
    );
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header
        style={{
          background: "#fff",
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "0 24px",
          borderBottom: "1px solid #f0f0f0",
          flexWrap: "wrap",
          minHeight: 64,
        }}
      >
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/")} type="text" />
        <Title level={4} style={{ margin: 0 }}>
          考试宝典{reportType === "weekly" ? "周" : "月"}报
        </Title>
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
            picker="week"
            value={selectedDate}
            onChange={(d) => d && setSelectedDate(d)}
            format={`YYYY [第]ww[周]`}
            style={{ width: 160 }}
          />
        ) : (
          <DatePicker
            picker="month"
            value={dayjs(month, "YYYY-MM")}
            onChange={(d) => d && setMonth(d.format("YYYY-MM"))}
          />
        )}
        {periodText && (
          <Tag icon={<CalendarOutlined />} color="blue" style={{ fontSize: 13, padding: "2px 10px" }}>
            {periodText}
          </Tag>
        )}
      </Header>

      <Content style={{ padding: 24, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 80 }}>
            <Spin size="large" />
          </div>
        ) : report ? (
          <>
            {renderSection("user_growth", "用户增长")}
            {renderSection("active", "用户活跃")}
            {renderSection("pay", "付费转化")}
            {renderSection("retention", "用户留存")}
            {renderSection("behavior", "用户行为")}
            <InsightText type={reportType} date={dateParam} />
          </>
        ) : (
          <div style={{ textAlign: "center", padding: 80 }}>
            <Title level={4} type="secondary">暂无报告数据</Title>
          </div>
        )}
      </Content>
    </Layout>
  );
}
