import React, { useState, useCallback, type FormEvent } from "react";
import { faTrash, faPlus } from "@fortawesome/free-solid-svg-icons";
import { Button } from "../../../shared/components/button";
import { IconButton } from "../../../shared/components/icon-button";
import { EntityListTable } from "../../../shared/components/entity-list-table";
import { SearchInput } from "../../../shared/components/search-input";
import { useToast } from "../../../shared/components/toast/use-toast";
import { useTokens } from "../../../core/hooks/use-tokens";
import { deleteUserToken, type UserToken } from "../../../core/services/token-service";
import { CreateTokenModal } from "./create-token-modal";
import type { ColumnConfig } from "../../../shared/types/table";

const formatDate = (dateString: string | null): string => {
  if (!dateString) return "-";
  try {
    return new Date(dateString).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateString;
  }
};

export const TokensList: React.FC = () => {
  const { tokens, isLoading, error, refresh } = useTokens();
  const { showToast } = useToast();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [submittedTerm, setSubmittedTerm] = useState("");
  const [deletingTokenId, setDeletingTokenId] = useState<number | null>(null);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setSearchTerm(e.target.value);
    },
    []
  );

  const handleSearchSubmit = useCallback((e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmittedTerm(searchTerm);
  }, [searchTerm]);

  const handleClearSearch = useCallback(() => {
    setSearchTerm("");
    setSubmittedTerm("");
  }, []);

  const handleDeleteToken = useCallback(
    async (token: UserToken) => {
      if (
        !window.confirm(
          `Are you sure you want to delete the token "${token.name}"? This cannot be undone.`
        )
      ) {
        return;
      }

      setDeletingTokenId(token.id);
      try {
        await deleteUserToken(token.id);
        showToast(`Token "${token.name}" deleted successfully`, "success");
        refresh();
      } catch (error) {
        console.error("Error deleting token:", error);
        showToast("Failed to delete token", "error");
      } finally {
        setDeletingTokenId(null);
      }
    },
    [showToast, refresh]
  );

  const handleTokenCreated = useCallback(() => {
    refresh();
  }, [refresh]);

  const filteredTokens = tokens.filter((token) =>
    token.name.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  const columns: ColumnConfig<UserToken>[] = [
    {
      header: "Name",
      render: (token) => (
        <span className="font-medium">{token.name}</span>
      ),
    },
    {
      header: "Created",
      render: (token) => formatDate(token.created_at),
      className: "w-44 flex-none",
    },
    {
      header: "Expires",
      render: (token) => formatDate(token.expires_at),
      className: "w-44 flex-none",
    },
    {
      header: "Last Used",
      render: (token) => formatDate(token.last_used_at),
      className: "w-44 flex-none",
    },
    {
      header: "",
      render: (token) => (
        <div className="invisible group-hover:visible">
          <IconButton
            icon={faTrash}
            onClick={() => void handleDeleteToken(token)}
            disabled={deletingTokenId === token.id}
            title={`Delete token "${token.name}"`}
          />
        </div>
      ),
      className: "w-12 flex-none",
    },
  ];

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-red-500 dark:text-red-400 mb-4">
          Failed to load tokens
        </p>
        <Button onClick={refresh} variant="secondary">
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center space-x-2 mb-4">
        <Button
          onClick={() => setIsCreateModalOpen(true)}
          variant="secondary"
          icon={faPlus}
        >
          Create Token
        </Button>
      </div>
      <div className="mb-2">
        <SearchInput
          value={searchTerm}
          onInputChange={handleInputChange}
          onSubmit={handleSearchSubmit}
          onClear={handleClearSearch}
          placeholder="Search tokens..."
        />
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-text-secondary dark:text-text-secondary-dark">
          Loading tokens...
        </div>
      ) : (
        <EntityListTable
          data={filteredTokens}
          columns={columns}
          searchTerm={submittedTerm}
        />
      )}

      <CreateTokenModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onTokenCreated={handleTokenCreated}
      />
    </div>
  );
};
