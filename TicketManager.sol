// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./contracts/ERC721Enumerable.sol";
import "./contracts/access/Ownable.sol";
import "./contracts/utils/Counters.sol";

contract TicketManager is ERC721Enumerable, Ownable {
    using Counters for Counters.Counter;
    Counters.Counter private _ticketIds;

    // Mapping from token ID to event ID or other metadata
    mapping(uint256 => string) private _tokenURIs;

    constructor() ERC721("Ticketera Ticket", "TKT") {}

    function safeMint(address to, string memory uri) public onlyOwner returns (uint256) {
        _ticketIds.increment();
        uint256 newItemId = _ticketIds.current();
        _safeMint(to, newItemId);
        _setTokenURI(newItemId, uri);
        return newItemId;
    }

    function _setTokenURI(uint256 tokenId, string memory _tokenURI) internal virtual {
        require(_exists(tokenId), "ERC721URIStorage: URI set for nonexistent token");
        _tokenURIs[tokenId] = _tokenURI;
    }

    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        require(_exists(tokenId), "ERC721URIStorage: URI query for nonexistent token");
        return _tokenURIs[tokenId];
    }
}
