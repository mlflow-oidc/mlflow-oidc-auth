import type { CurrentUser } from "../../../shared/types/user";

interface UserDetailsCardProps {
  currentUser: CurrentUser;
}

export const UserDetailsCard: React.FC<UserDetailsCardProps> = ({
  currentUser,
}) => {
  const rowClasses =
    "flex flex-row items-center min-h-(--table-row-height) px-1 hover:bg-table-row-hover dark:hover:bg-table-row-hover transition-colors duration-150 border-b border-btn-secondary-border dark:border-btn-secondary-border-dark";
  const labelClasses =
    "w-1/3 font-semibold text-text-primary dark:text-text-primary-dark";
  const valueClasses =
    "w-2/3 text-ui-text dark:text-ui-text-dark font-mono break-all";

  return (
    <div className="flex flex-col text-sm">
      <div className="divide-y divide-btn-secondary-border dark:divide-btn-secondary-border-dark">
        {[
          { label: "Display Name", value: currentUser.display_name },
          { label: "Username", value: currentUser.username },
        ].map(({ label, value }) => (
          <div key={label} className={rowClasses}>
            <div className={labelClasses}>{label}</div>
            <div className={valueClasses}>{value || "N/A"}</div>
          </div>
        ))}

        <div className={rowClasses}>
          <div className={labelClasses}>Groups</div>
          <div className="w-2/3">
            {currentUser.groups && currentUser.groups.length > 0 ? (
              <div className="flex flex-wrap gap-2 py-0.5">
                {currentUser.groups.map((group) => (
                  <span
                    key={group.id}
                    className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-btn-secondary-bg dark:bg-btn-secondary-bg-dark text-text-primary dark:text-text-primary-dark border border-btn-secondary-border dark:border-btn-secondary-border-dark"
                  >
                    {group.group_name}
                  </span>
                ))}
              </div>
            ) : (
              <p className="italic text-text-primary dark:text-text-primary-dark opacity-60">
                This user is not a member of any groups.
              </p>
            )}
          </div>
        </div>

        {currentUser.is_admin && (
          <div className="p-1 mt-2 min-h-(--table-row-height) flex items-center">
            <p className="text-logo text-base font-semibold">
              You have administrator privileges. Additional management options
              are available to you.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
