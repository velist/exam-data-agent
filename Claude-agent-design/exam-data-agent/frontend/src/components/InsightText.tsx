import { useEffect, useMemo, useState } from "react";
import { Alert, Card, Spin } from "antd";
import { BulbOutlined, LoadingOutlined } from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import { InsightParams, InsightStatusEvent, streamInsight } from "../api";

interface Props {
  params: InsightParams;
}

export default function InsightText({ params }: Props) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<InsightStatusEvent>({
    stage: "querying",
    text: "正在查询数据...",
  });

  useEffect(() => {
    setText("");
    setError("");
    setLoading(true);
    setStatus({ stage: "querying", text: "正在查询数据..." });
    const cancel = streamInsight(
      params,
      (chunk) => setText((prev) => prev + chunk),
      () => setLoading(false),
      (msg) => setError(msg),
      (nextStatus) => setStatus(nextStatus),
    );
    return cancel;
  }, [params.type, params.date, params.start, params.end]);

  const steps = useMemo<InsightStatusEvent[]>(
    () => [
      { stage: "querying", text: "正在查询数据..." },
      { stage: "analyzing", text: "正在分析数据..." },
      { stage: "generating", text: "正在生成分析..." },
    ],
    [],
  );

  const activeStepIndex = steps.findIndex((item) => item.stage === status.stage);
  const hasGeneratedText = text.trim().length > 0;
  const allStepsCompleted = !loading && hasGeneratedText;

  return (
    <Card
      className="report-insight"
      title={
        <span className="report-insight__title">
          <BulbOutlined className="report-insight__title-icon" />
          AI 分析洞察
        </span>
      }
      styles={{
        header: { borderBottom: "none", minHeight: 56 },
      }}
    >
      <div className="report-insight__loading">
        <div className="report-insight__status-card">
          <div className="report-insight__status-header">
            <span className="report-insight__status-dot" />
            <span className="report-insight__status-text">{loading ? status.text : hasGeneratedText ? "分析已生成" : "等待生成分析"}</span>
            {loading && <Spin indicator={<LoadingOutlined spin />} size="small" />}
          </div>
          <div className="report-insight__steps" role="status" aria-live="polite">
            {steps.map((step, index) => {
              const completed = allStepsCompleted || activeStepIndex > index;
              const active = !allStepsCompleted && activeStepIndex === index && loading;
              return (
                <div
                  key={step.stage}
                  className={[
                    "report-insight__step",
                    completed ? "report-insight__step--done" : "",
                    active ? "report-insight__step--active" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <span className="report-insight__step-marker">{completed ? "✓" : index + 1}</span>
                  <span className="report-insight__step-label">{completed ? "已生成" : step.text}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      {error && !text && (
        <Alert className="report-insight__error" type="error" showIcon message={error} />
      )}
      <div className="report-insight__markdown markdown-report">
        <ReactMarkdown>{text}</ReactMarkdown>
        {loading && <span className="report-insight__cursor">|</span>}
        {!loading && !text && <p>暂无洞察内容</p>}
      </div>
    </Card>
  );
}
