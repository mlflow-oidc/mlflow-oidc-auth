import React, { useState, useCallback } from "react";
import { faTrash, faPlus } from "@fortawesome/free-solid-svg-icons";
import { Button } from "../../../shared/components/button";
import { IconButton } from "../../../shared/components/icon-button";
import { EntityListTable } from "../../../shared/components/entity-list-table";
import { SearchInput } from "../../../shared/components/search-input";
import { useToast } from "../../../shared/components/toast/use-toast";
import { useSearch } from "../../../core/hooks/use-search";
import { useTokens } from "../../../core/hooks/use-tokens";
import { deleteUserToken, type UserToken } from "../../../core/services/token-service";
import { CreateTokenModal } from "./create-token-modal";
import { DeleteTokenModal } from "./delete-token-modal";
import type { ColumnConfig } from "../../../shared/types/table";

const formatDate = (dateString: string | null): string => {
  if (!dateString) return "-";
  try {
    return new Date(dateString).toLocaleString(undefined, {
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
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [tokenToDelete, setTokenToDelete] = useState<UserToken | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDeleteClick = useCallback((token: UserToken) => {
    setTokenToDelete(token);
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (!tokenToDelete) return;

    setIsDeleting(true);
    try {
      await deleteUserToken(tokenToDelete.id);
      showToast(`Token "${tokenToDelete.name}" deleted successfully`, "success");
      refresh();
      setTokenToDelete(null);
    } catch (error) {
      console.error("Error deleting token:", error);
      showToast("Failed to delete token", "error");
    } finally {
      setIsDeleting(false);
    }
  }, [tokenToDelete, showToast, refresh]);

  const handleDeleteCancel = useCallback(() => {
    setTokenToDelete(null);
  }, []);

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
      header: "Actions",
      render: (token) => (
        <div className="invisible group-hover:visible">
          <IconButton
            icon={faTrash}
            onClick={() => handleDeleteClick(token)}
            disabled={isDeleting && tokenToDelete?.id === token.id}
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
    <>
      <div className="mb-4 flex items-center gap-6">
        <SearchInput
          value={searchTerm}
          onInputChange={handleInputChange}
          onSubmit={handleSearchSubmit}
          onClear={handleClearSearch}
          placeholder="Search tokens..."
        />
        <Button
          onClick={() => setIsCreateModalOpen(true)}
          variant="secondary"
          icon={faPlus}
          className="whitespace-nowrap h-8 mb-1 mt-2"
        >
          Create Token
        </Button>
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

      <DeleteTokenModal
        isOpen={tokenToDelete !== null}
        onClose={handleDeleteCancel}
        onConfirm={() => void handleDeleteConfirm()}
        token={tokenToDelete}
        isProcessing={isDeleting}
      />
    </>
  );
};
