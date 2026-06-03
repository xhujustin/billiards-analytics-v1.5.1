import { ChevronDown } from 'lucide-react';
import type { DataSection } from '../MobilePrototypeApp';

export const dataOptions: DataSection[] = ['總覽', '對戰記錄', '進攻數據', '防守數據', '球型表現', '走位分析', '失誤分析'];

export default function DropdownSelector({
  value,
  onChange,
}: {
  value: DataSection;
  onChange: (value: DataSection) => void;
}) {
  return (
    <label className="relative inline-flex">
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as DataSection)}
        className="h-10 appearance-none rounded-xl border border-cue-line bg-white py-0 pl-4 pr-10 text-sm font-bold text-cue-ink shadow-sm outline-none"
      >
        {dataOptions.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-cue-ink" size={16} />
    </label>
  );
}
