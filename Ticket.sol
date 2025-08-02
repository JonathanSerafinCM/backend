// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Ticket {
    address public owner;
    uint256 public ticketId;

    constructor(uint256 _ticketId) {
        owner = msg.sender;
        ticketId = _ticketId;
    }
}
