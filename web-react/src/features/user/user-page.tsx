import Header from "../../shared/components/header";

export const UserPage = () => {
  // Placeholder for the logged-in user's name
  const userName = "Alice";

  return (
    <>
      <Header userName={userName} />
      <div
        className="
          p-8 shadow-md min-h-screen
          bg-[rgb(255,255,255)] text-[rgb(17,23,28)]
          dark:bg-[rgb(17,23,28)] dark:text-[rgb(232,236,240)]
        "
      >
        <h1 className="mt-8 text-3xl font-bold">Dark Mode Test</h1>
        <p className="mt-4">
          This is some sample text to see the light/dark mode toggle in action.
        </p>

        <div className="p-6 text-center mt-12">
          <h2 className="text-2xl font-bold mb-4">User Page</h2>
          <p>This is a placeholder for the User page.</p>
        </div>
      </div>
    </>
  );
};

export default UserPage;
