import DarkModeToggle from "./shared/components/dark-mode-toggle";

export default function App() {
  return (
    <div className="min-h-screen bg-white dark:bg-gray-900 text-black dark:text-white p-8">
      <DarkModeToggle />
      <h1 className="mt-8 text-3xl font-bold">Dark Mode Test</h1>
      <p className="mt-4">
        This is some sample text to see the light/dark mode toggle in action.
      </p>
    </div>
  );
}
