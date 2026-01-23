import MainLayout from "../../core/components/main-layout";

export default function ForbiddenPage() {
  return (
    <MainLayout>
      <div className="flex flex-col h-full items-center justify-center px-4">
        <h2 className="text-4xl sm:text-5xl font-extrabold mb-4 text-logo">
          Access Denied
        </h2>
        <p className="text-lg text-center max-w-lg mb-10 text-text-primary dark:text-text-primary-dark">
          Sorry, you do not have permission to view this page.
        </p>
      </div>
    </MainLayout>
  );
}
