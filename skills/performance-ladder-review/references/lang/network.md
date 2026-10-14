# Network / browser performance rules

Source: High Performance Browser Networking (Grigorik). Read when code does HTTP/network/browser work. These are rung-0/rung-2 moves at the network layer.

## Rules
1. **Latency dominates bandwidth.** Above a few Mbps, more bandwidth barely helps latency-bound work; the round trip is the wall. "No bit is faster than a bit not sent." Humans notice lag past ~100-200 ms.
2. **Connection reuse is the critical optimization.** The TCP three-way handshake makes new connections expensive; keep-alive / pooling eliminates a full round trip per request. (This is the mechanism behind the "chatty API" catalog entry.)
3. **Eliminate round trips, in priority order:** reuse connections -> TLS session resumption (saves ~1 RTT for repeat visits) -> move the server closer (CDN/edge) -> then compress. Each is "do it less often" at the network layer.
4. **TLS record <= one TCP segment.** Small records add overhead; large records add latency. A tunable most people never touch.
5. **Batch requests / avoid N round trips for one screen.** A single batch endpoint beats N chatty calls: the network form of rung 2.

New TCP+TLS connection setup costs ~2-3 round trips. That is the number that makes connection reuse's payoff legible.
