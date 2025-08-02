// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./contracts/utils/Counters.sol";

contract TicketManager {
    using Counters for Counters.Counter;
    Counters.Counter private _ticketIds;

    mapping(uint256 => address) public ticketOwners;
    address public admin;

    constructor() {
        admin = msg.sender;
    }

    function createTicket(address owner) public returns (uint256) {
        require(msg.sender == admin, "Only admin can create tickets");
        _ticketIds.increment();
        uint256 newItemId = _ticketIds.current();
        ticketOwners[newItemId] = owner;
        return newItemId;
    }
}
