import type { CurrentUser } from "../../../shared/types/user";

interface UserDetailsCardProps {
  currentUser: CurrentUser;
}

export const UserDetailsCard: React.FC<UserDetailsCardProps> = ({
  currentUser,
}) => {
  return (
    <div className="max-w-2xl mx-auto">
      <ul className="divide-y divide-gray-200 dark:divide-gray-700 border border-gray-200 dark:border-gray-700 rounded-lg px-4 bg-ui-control-bg dark:bg-ui-secondary-bg-dark shadow-md">
        {[
          { label: "Display Name", value: currentUser.display_name },
          { label: "Username", value: currentUser.username },
        ].map(({ label, value }) => (
          <li key={label} className="flex justify-between items-center py-3">
            <strong className="font-medium text-gray-700 dark:text-gray-300">
              {label}:
            </strong>
            <span className="text-right text-ui-text dark:text-ui-text-dark font-mono break-all ml-4">
              {value || "N/A"}
            </span>
          </li>
        ))}

        {currentUser.is_admin && (
          <div className="py-2 px-3 my-2 border-none">
            <p className="text-sm text-logo">
              You have <b>administrator privileges</b>. Additional management
              options are available to you.
            </p>
          </div>
        )}

        <li className="py-3 border-t border-gray-200 dark:border-gray-700">
          <strong className="font-medium block mb-2 text-gray-700 dark:text-gray-300">
            Groups:
          </strong>
          {currentUser.groups && currentUser.groups.length > 0 ? (
            <ul className="list-disc list-inside ml-4 text-sm space-y-1">
              {currentUser.groups.map((group) => (
                <li
                  key={group.id}
                  className="text-ui-text dark:text-ui-text-dark"
                >
                  {group.group_name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm italic text-gray-500 dark:text-gray-400 ml-4">
              This user is not a member of any groups.
            </p>
          )}
        </li>
      </ul>

      <p className="text-xs pt-4 text-center text-gray-500 dark:text-gray-400">
        {currentUser.password_expiration == null
          ? "You have no access token yet."
          : `🔑 Your token expires on: ${new Date(
              currentUser.password_expiration
            ).toLocaleDateString()} at ${new Date(
              currentUser.password_expiration
            ).toLocaleTimeString()}`}
      </p>
    </div>
  );
};
