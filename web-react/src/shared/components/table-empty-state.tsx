export function TableEmptyState({ searchTerm }: { searchTerm: string }) {
  const message = searchTerm
    ? `No items found for "${searchTerm}"`
    : "No items found";
  return (
    <p className="text-btn-secondary-text dark:text-btn-secondary-text-dark italic p-4">
      {message}
    </p>
  );
}
