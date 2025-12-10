export default function ResultsHeader({ count }: { count: number }) {
  return <h3 className="text-base font-medium p-1 mb-1">Results ({count})</h3>;
}
