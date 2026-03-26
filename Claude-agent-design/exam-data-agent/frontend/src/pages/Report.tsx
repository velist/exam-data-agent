import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Layout, DatePicker, Segmented, Row, Col, Spin, Button, Typography, Divider } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import MetricCard from "../components/MetricCard";
import TrendChart from "../components/TrendChart";
import InsightText from "../components/InsightText";
import { getWeeklyReport, getMonthlyReport, ReportResponse } from "../api";
const { Header, Content } = Layout;
const { Title } = Typography;
export default function Report() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [reportType, setReportType] = useState<"weekly" | "monthly">((searchParams.get("type") as "weekly" | "monthly") || "weekly");
  const [date, setDate] = useState(dayjs().format("YYYY-MM-DD"));
  const [month, setMonth] = useState(dayjs().format("YYYY-MM"));
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const currentDateParam = reportType === "weekly" ? date : month;
  useEffect(() => {
    setLoading(true);
    (reportType === "weekly" ? getWeeklyReport(date) : getMonthlyReport(month)).then(setReport).catch(() => setReport(null)).finally(() => setLoading(false));
  }, [reportType, date, month]);
  const renderSection = (key: string, title: string) => {
    const section = report?.sections?.[key];
    if (!section || !section.metrics) return null;
    const metrics = Object.values(section.metrics) as any[];
    const metricKeys = Object.keys(section.metrics);
    const trend = section.trend || [];
    const xData = trend.map((t: any) => t.start || t.end || "");
    return (<div key={key} style={{ marginBottom: 32 }}><Title level={5}>{title}</Title><Row gutter={[16, 16]}>{metrics.map((m: any) => (<Col key={m.label} xs={12} sm={8} md={6}><MetricCard data={m} /></Col>))}</Row>{trend.length > 1 && (<TrendChart title={`${title}趋势`} xData={xData} series={metrics.map((m: any, idx: number) => ({ name: m.label, data: trend.map((t: any) => t[metricKeys[idx]] || 0) }))} />)}<Divider /></div>);
  };
  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header style={{ background: "#fff", display: "flex", alignItems: "center", gap: 16, padding: "0 24px", borderBottom: "1px solid #f0f0f0", flexWrap: "wrap" }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/")} type="text" />
        <Title level={4} style={{ margin: 0 }}>考试宝典{reportType === "weekly" ? "周" : "月"}报</Title>
        <Segmented value={reportType} options={[{ label: "周报", value: "weekly" }, { label: "月报", value: "monthly" }]} onChange={(v) => setReportType(v as "weekly" | "monthly")} />
        {reportType === "weekly" ? <DatePicker value={dayjs(date)} onChange={(d) => d && setDate(d.format("YYYY-MM-DD"))} /> : <DatePicker picker="month" value={dayjs(month, "YYYY-MM")} onChange={(d) => d && setMonth(d.format("YYYY-MM"))} />}
      </Header>
      <Content style={{ padding: 24, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        {loading ? <div style={{ textAlign: "center", padding: 80 }}><Spin size="large" /></div> : report ? (
          <>{renderSection("user_growth", "用户增长")}{renderSection("active", "用户活跃")}{renderSection("pay", "付费转化")}{renderSection("retention", "用户留存")}{renderSection("behavior", "用户行为")}<InsightText type={reportType} date={currentDateParam} /></>
        ) : <div style={{ textAlign: "center", padding: 80 }}><Title level={4} type="secondary">暂无报告数据</Title></div>}
      </Content>
    </Layout>
  );
}
