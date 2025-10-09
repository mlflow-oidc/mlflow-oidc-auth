import { Outlet } from "react-router";

export const ManagePage = () => {
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-4">Manage Page</h1>
      <p>This is a placeholder for the Manage feature area.</p>
      <Outlet />
    </div>
  );
};

export default ManagePage;
