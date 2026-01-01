export default function PageContainer({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <h2 className="flex-shrink-0 text-2xl font-medium mb-3 text-center">
        {title}
      </h2>

      <>{children}</>
    </>
  );
}
