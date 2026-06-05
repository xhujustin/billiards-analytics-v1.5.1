import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts';

export default function DonutChart({ value }: { value: number }) {
  const safeValue = Math.max(0, Math.min(100, value));
  const data = [
    { name: '達成', value: safeValue },
    { name: '剩餘', value: 100 - safeValue },
  ];

  return (
    <div className="relative h-32 w-32">
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" innerRadius={42} outerRadius={58} startAngle={90} endAngle={-270} stroke="none">
            <Cell fill="#4F46E5" />
            <Cell fill="#E5E7EB" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 grid place-items-center text-lg font-black text-cue-ink">{safeValue}%</div>
    </div>
  );
}
