# External daily series

Downloaded from Yahoo Finance chart API on 2026-11-28 for the new-family
programme.  Each file contains `date, open, high, low, close, adjclose,
volume` daily rows from 2015-01-02 through 2026-09-21 (some symbols end
earlier).  `adjclose` is used for total-return signals; the TQQQ execution
panel remains the local 1-minute QQQ/TQQQ/BIL archive.

Symbols: `^VIX`, `^VIX3M`, `^TNX`, `^IRX`, `^TYX`, `^FVX`, `^MOVE`, `^SKEW`,
`^VVIX`, `TLT`, `IEF`, `SHY`, `HYG`, `LQD`, `TIP`, `UUP`, `GLD`, `USO`,
`CPER`, `XLU`, `XLK`, `XLE`, `XLF`, `XLV`, `XLY`, `XLP`, `XLI`, `XLB`,
`XLRE`, `XLC`, `IWM`, `EEM`, `EFA`, `RSP`, `SPY`, `QUAL`, `MTUM`, `GDX`,
`SLV`, `SMH`, `XBI`, `XHB`, `XRT`, `BTC-USD`, `JPY=X`.

Fetch script: `research/fetch_external.py`.  Loader/alignment helper:
`research/external.py`.  The external series are signal inputs only; the
traded assets remain TQQQ/BIL/QQQ on the local adjusted 1-minute panel.
