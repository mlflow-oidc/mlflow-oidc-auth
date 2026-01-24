export default function PageContainer({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <h2 className="shrink-0 text-xl font-semibold mb-3">
        {title}
      </h2>

      <>{children}</>
    </>
  );
}
