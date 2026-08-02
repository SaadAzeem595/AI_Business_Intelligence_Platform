"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { BaseChart } from "@/shared/components/data-display/BaseChart";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { TrendingUp, Settings2, Sparkles, AlertCircle } from "lucide-react";

import { useForecast } from "@/features/analytics/hooks/useForecast";

interface ForecastModelMetric {
  metric: string;
  arimaValue: string;
  prophetValue: string;
}

export default function ForecastingPage() {
  const [modelType, setModelType] = useState<"ARIMA" | "Prophet">("Prophet");
  const [confidence, setConfidence] = useState(95);
  const [periods, setPeriods] = useState(6);

  const { forecastData, metrics, isLoading, refetch } = useForecast(modelType, confidence, periods);

  const columns: Column<any>[] = [
    {
      header: "Performance Evaluator",
      accessorKey: "metric",
      cell: (row) => <span className="font-semibold text-foreground">{row.metric}</span>,
    },
    { header: "ARIMA Model", accessorKey: "arimaValue" },
    {
      header: "Prophet Model (Recommended)",
      accessorKey: "prophetValue",
      cell: (row) => <span className="font-bold text-brand-indigo">{row.prophetValue}</span>,
    },
  ];

  const handleRunForecast = () => {
    refetch();
  };

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Time Series Forecasting</h1>
        <p className="text-xs text-muted-foreground">Apply autoregressive algorithms on numerical datasets columns to project business trends.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Side: Parameters Slider Panel */}
        <Card className="border-border/80 lg:col-span-1 h-fit">
          <CardHeader>
            <CardTitle className="text-base font-bold flex items-center gap-1.5">
              <Settings2 className="h-4.5 w-4.5 text-brand-indigo" /> Forecast Tuner
            </CardTitle>
            <CardDescription className="text-[11px]">Adjust modeling properties.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground">Select forecasting engine</label>
              <div className="grid grid-cols-2 border border-border/80 rounded-md overflow-hidden p-0.5 bg-muted/20">
                {(["ARIMA", "Prophet"] as const).map((type) => (
                  <button
                    key={type}
                    onClick={() => setModelType(type)}
                    className={`text-[10px] font-bold py-1.5 rounded-md transition-all cursor-pointer ${
                      modelType === type
                        ? "bg-card text-foreground shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-muted-foreground">Confidence level</span>
                <span className="text-brand-indigo">{confidence}%</span>
              </div>
              <input
                type="range"
                min="80"
                max="99"
                value={confidence}
                onChange={(e) => setConfidence(Number(e.target.value))}
                className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-brand-indigo"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground">Periods (Months)</label>
              <select
                value={periods}
                onChange={(e) => setPeriods(Number(e.target.value))}
                className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground/80 cursor-pointer"
              >
                {[3, 6, 12, 24].map((p) => (
                  <option key={p} value={p}>
                    Project {p} Months
                  </option>
                ))}
              </select>
            </div>

            <Button onClick={handleRunForecast} disabled={isLoading} className="w-full mt-4" variant="brand" size="sm">
              {isLoading ? "Recomputing trends..." : "Run Forecast Model"}
            </Button>
          </CardContent>
        </Card>

        {/* Right Side: Projections Line Chart */}
        <div className="lg:col-span-3 space-y-6">
          <Card className="border-border/80">
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div>
                <CardTitle className="text-base font-bold">Sales Projections Curve</CardTitle>
                <CardDescription className="text-[11px]">Dotted lines indicate model trends outputs with {confidence}% intervals.</CardDescription>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="h-2 w-2 rounded-full bg-brand-indigo" /> Actuals
                <span className="h-2 w-2 rounded-full bg-emerald-500" /> Predictions
              </div>
            </CardHeader>
            <CardContent>
              <BaseChart
                type="line"
                data={forecastData}
                xKey="date"
                yKeys={["actual", "forecast"]}
                colors={["var(--color-brand-indigo)", "#10b981"]}
              />
            </CardContent>
          </Card>

          {/* Model metrics table */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-brand-indigo" /> Model Evaluation Metrics
            </h2>
            <BaseTable columns={columns as any} data={metrics} isLoading={isLoading} />
          </div>
        </div>
      </div>
    </div>
  );
}
