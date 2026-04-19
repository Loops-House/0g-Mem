// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MemoryPermissionRegistry
 * @notice On-chain permission registry for 0g Mem agents.
 *
 * Allows a user (wallet) to grant specific agents READ or WRITE access
 * to their memory store. Permissions are checked via view calls — free, no gas.
 *
 * Deployed on: 0g Galileo Testnet
 */
contract MemoryPermissionRegistry {

    // ─── Enums ────────────────────────────────────────────────────────────────

    enum Permission {
        NONE,   // No access
        READ,   // Can retrieve memories
        WRITE,  // Can write memories (session batching)
        ADMIN   // Can grant/revoke other agents
    }

    // ─── Storage ──────────────────────────────────────────────────────────────

    /// @notice user → agent → permission level
    mapping(address => mapping(address => Permission)) public permissions;

    /// @notice user → agent → blob_id[] — optional per-blob scoping
    mapping(address => mapping(address => bytes32[])) public agentShardIds;

    /// @notice Whether an agent has full (unscoped) access
    mapping(address => mapping(address => bool)) public hasFullAccess;

    // ─── Events ───────────────────────────────────────────────────────────────

    event AccessGranted(
        address indexed user,
        address indexed agent,
        Permission permission,
        bool fullAccess
    );

    event AccessRevoked(
        address indexed user,
        address indexed agent
    );

    // ─── External functions ────────────────────────────────────────────────────

    /**
     * @notice Grant an agent access to the caller's memory.
     * @param agent    Agent wallet address.
     * @param level    READ, WRITE, or ADMIN.
     * @param shardIds Optional list of blob_ids to limit scope. Empty = full access.
     */
    function grantAccess(
        address agent,
        Permission level,
        bytes32[] calldata shardIds
    ) external {
        require(agent != address(0), "MemoryPermissionRegistry: zero agent");
        require(agent != msg.sender, "MemoryPermissionRegistry: cannot self-grant");
        require(uint8(level) >= uint8(Permission.READ), "MemoryPermissionRegistry: invalid level");

        permissions[msg.sender][agent] = level;
        hasFullAccess[msg.sender][agent] = shardIds.length == 0;

        // Store scoped blob IDs
        if (shardIds.length > 0) {
            delete agentShardIds[msg.sender][agent];
            for (uint i = 0; i < shardIds.length; i++) {
                agentShardIds[msg.sender][agent].push(shardIds[i]);
            }
        } else {
            delete agentShardIds[msg.sender][agent];
        }

        emit AccessGranted(msg.sender, agent, level, shardIds.length == 0);
    }

    /**
     * @notice Revoke all access for an agent.
     * @param agent Agent wallet address.
     */
    function revokeAccess(address agent) external {
        require(agent != address(0), "MemoryPermissionRegistry: zero agent");

        delete permissions[msg.sender][agent];
        delete hasFullAccess[msg.sender][agent];
        delete agentShardIds[msg.sender][agent];

        emit AccessRevoked(msg.sender, agent);
    }

    /**
     * @notice Check what permission level an agent has for a user.
     * @param user   User wallet address.
     * @param agent  Agent wallet address.
     * @return Permission level (NONE / READ / WRITE / ADMIN)
     */
    function getPermission(
        address user,
        address agent
    ) external view returns (Permission) {
        return permissions[user][agent];
    }

    /**
     * @notice Check if an agent has full (unscoped) access to a user's memory.
     * @param user   User wallet address.
     * @param agent  Agent wallet address.
     * @return bool  True if full access.
     */
    function hasFullMemoryAccess(
        address user,
        address agent
    ) external view returns (bool) {
        return hasFullAccess[user][agent];
    }

    /**
     * @notice Check if an agent has access to a specific blob.
     * @param user    User wallet address.
     * @param agent   Agent wallet address.
     * @param blobId  The blob_id (bytes32 content hash) to check.
     * @return bool   True if the agent has access to this blob.
     */
    function hasBlobAccess(
        address user,
        address agent,
        bytes32 blobId
    ) external view returns (bool) {
        Permission perm = permissions[user][agent];
        if (perm == Permission.NONE) return false;
        if (hasFullAccess[user][agent]) return true;

        // Check if blobId is in the scoped list
        bytes32[] storage shards = agentShardIds[user][agent];
        for (uint i = 0; i < shards.length; i++) {
            if (shards[i] == blobId) return true;
        }
        return false;
    }

    /**
     * @notice List all agents that have access for a user (view only — gas free).
     * @param user    User wallet address.
     * @param cursor  Starting index for pagination.
     * @param limit   Max results to return.
     * @return agents  Array of agent addresses.
     * @return perms   Corresponding permission levels.
     */
    function listAgents(
        address user,
        uint cursor,
        uint limit
    ) external view returns (
        address[] memory agents,
        Permission[] memory perms
    ) {
        // This requires knowing the total count which isn't stored directly.
        // A practical implementation would maintain a secondary index.
        // For MVP, this returns an empty result — agents can be checked individually.
        agents = new address[](0);
        perms = new Permission[](0);
    }
}
