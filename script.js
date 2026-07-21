function fmtMoney(v){
  const n = Number(v);
  if (!Number.isFinite(n)) return "0,00 $";
  return n.toLocaleString("ru-RU",{minimumFractionDigits:2,maximumFractionDigits:2})+" $";
}

function fmtToken(v){
  const n = Number(v);
  if (!Number.isFinite(n)) return "0";
  return n.toLocaleString("ru-RU",{minimumFractionDigits:2,maximumFractionDigits:6});
}

function ellipsize(s){
  if (!s) return "—";
  const t = String(s).trim();
  if (t.length <= 18) return t;
  return t.slice(0,6)+"..."+t.slice(-6);
}

function getBaseFromScript(){
  const cs = document.currentScript && document.currentScript.src ? document.currentScript.src : "";
  const fallback = window.location.href;
  const u = cs ? new URL(cs) : new URL(fallback);
  return new URL(".", u);
}

const BASE = getBaseFromScript();

function assetUrl(p){
  return new URL(p, BASE).toString();
}

function coinIcon(coin){
  return coin === "USDC" ? assetUrl("img/usdc.png") : assetUrl("img/usdt.png");
}

function netIcon(net){
  return net === "ERC20" ? assetUrl("img/ethereum.png") : assetUrl("img/tron.png");
}

function netName(net){
  return net === "ERC20" ? "Ethereum" : "Tron";
}

function getRecordId(){
  const sp = new URLSearchParams(window.location.search || "");
  const id = (sp.get("id") || sp.get("rid") || "").trim();
  if (id) return id;
  const s = window.location.search || "";
  if (!s || s === "?") return "";
  return s.startsWith("?") ? s.slice(1).trim() : "";
}

async function loadRecord(){
  const id = getRecordId();
  if (!id) return;

  const title = document.getElementById("rxTitle");

  const jsonUrl = new URL("data/records.json", BASE);
  jsonUrl.searchParams.set("ts", String(Date.now()));

  let store;
  try{
    const r = await fetch(jsonUrl.toString(), { cache: "no-store" });
    if (!r.ok) throw new Error("fetch");
    store = await r.json();
  }catch{
    if (title) title.textContent = "Not found";
    return;
  }

  const d = store && typeof store === "object" ? store[id] : null;
  if (!d) {
    if (title) title.textContent = "Not found";
    return;
  }

  const amountUsd = (d.amountUsd ?? d.amountTokens);
  const totalUsd = (d.totalUsd ?? amountUsd);

  const coinEl = document.getElementById("coinIcon");
  if (coinEl) { coinEl.src = coinIcon(d.coin); coinEl.alt = d.coin || "coin"; }

  const netEl = document.getElementById("networkIcon");
  if (netEl) { netEl.src = netIcon(d.network); netEl.alt = d.network || "network"; }

  const usdAmount = document.getElementById("usdAmount");
  if (usdAmount) usdAmount.textContent = fmtMoney(amountUsd);

  const tokenLine = document.getElementById("tokenLine");
  if (tokenLine) tokenLine.textContent = fmtToken(d.amountTokens) + " " + (d.coin || "");

  const walletName = document.getElementById("walletName");
  if (walletName) walletName.textContent = d.walletName || "—";

  const fromAddr = document.getElementById("fromAddr");
  if (fromAddr) fromAddr.textContent = ellipsize(d.fromAddress);

  const toAddr = document.getElementById("toAddr");
  if (toAddr) toAddr.textContent = ellipsize(d.toAddress);

  const networkNameEl = document.getElementById("networkName");
  if (networkNameEl) networkNameEl.textContent = netName(d.network);

  const discountBadge = document.getElementById("discountBadge");
  if (discountBadge) discountBadge.textContent = String(d.discountPercent ?? 0) + "% Discount";

  const feeUsd = document.getElementById("feeUsd");
  if (feeUsd) feeUsd.textContent = fmtMoney(d.feeUsd);

  const feeTokens = document.getElementById("feeTokens");
  if (feeTokens) feeTokens.textContent = fmtToken(d.feeTokens) + " " + (d.coin || "");

  const totalCost = document.getElementById("totalCost");
  if (totalCost) totalCost.textContent = fmtMoney(totalUsd);
}

loadRecord();
