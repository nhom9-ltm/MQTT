/* Trang quản trị — Luật tự động: thêm / sửa / xóa / bật-tắt luật (API ghi backend/config/rules.json).
 * Kích hoạt nhập bằng form; điều kiện phụ và hành động nhập JSON (server kiểm tra kỹ và báo lỗi tiếng Việt). */
(() => {
  const { call, esc, toast } = window.Admin;
  const $ = (id) => document.getElementById(id);

  let rules = [];
  let devices = [];
  let editing = null;           // mã luật đang sửa, null = thêm mới

  const fmtValue = (v) => (typeof v === "string" ? `"${v}"` : String(v));
  function triggerText(t) {
    if (!t) return "";
    if (t.at) return `Lúc ${t.at}`;
    return `${t.device} · ${t.field} ${t.op || "=="} ${fmtValue(t.value)}${t.for ? ` (giữ ${t.for}s)` : ""}`;
  }

  // ---------------- bảng ----------------
  function render() {
    $("rulesBody").innerHTML = rules.length ? rules.map((r) => {
      const on = r.enabled !== false;
      return `<tr class="${on ? "" : "disabled"}">
        <td><button type="button" class="sw sm" role="switch" aria-checked="${on}" aria-label="Bật/tắt luật" data-toggle="${esc(r.id)}"><i></i></button></td>
        <td class="wrap">${esc(r.name)}<small>${esc(r.id)}</small></td>
        <td class="wrap"><code>${esc(triggerText(r.trigger))}</code>${r.conditions?.length ? `<small>+ ${r.conditions.length} điều kiện phụ</small>` : ""}</td>
        <td class="num">${r.actions?.length || 0}</td>
        <td class="actions">
          <button type="button" class="btn sm" data-edit="${esc(r.id)}">Sửa</button>
          <button type="button" class="btn sm danger" data-del="${esc(r.id)}">Xóa</button>
        </td></tr>`;
    }).join("") : '<tr><td colspan="5" class="muted">Chưa có luật nào.</td></tr>';
  }

  async function load() {
    try {
      [rules, devices] = await Promise.all([call("/api/admin/rules"), call("/api/admin/devices")]);
      Admin.setBadge("rules", rules.length);
      render();
    } catch (e) {
      $("rulesBody").innerHTML = `<tr><td colspan="5" class="muted">${esc(e.message)}</td></tr>`;
    }
  }

  // ---------------- form ----------------
  const f = {
    dialog: $("ruleDialog"), title: $("ruleTitle"), error: $("ruleError"), id: $("ruleId"), name: $("ruleName"),
    desc: $("ruleDesc"), kind: $("trigKind"), device: $("trigDevice"), field: $("trigField"), op: $("trigOp"),
    value: $("trigValue"), for: $("trigFor"), at: $("trigAt"), conds: $("ruleConds"), actions: $("ruleActions"),
    cooldown: $("ruleCooldown"), enabled: $("ruleEnabled"),
  };
  let kind = "device";

  function setKind(k) {
    kind = k;
    f.kind.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.kind === k));
    f.dialog.querySelector(".trig-device").hidden = k !== "device";
    f.dialog.querySelector(".trig-at").hidden = k !== "at";
  }
  f.kind.addEventListener("click", (e) => { const b = e.target.closest("button[data-kind]"); if (b) setKind(b.dataset.kind); });

  /* "true"/"false" → boolean, số → number, còn lại là chuỗi (bỏ dấu nháy nếu có). */
  function parseValue(text) {
    const s = text.trim();
    if (s === "true" || s === "false") return s === "true";
    if (s !== "" && !Number.isNaN(Number(s))) return Number(s);
    return s.replace(/^"(.*)"$/, "$1");
  }
  const pretty = (v) => (v && v.length ? JSON.stringify(v, null, 2) : "");

  function parseJsonList(text, label) {
    if (!text.trim()) return [];
    let v;
    try { v = JSON.parse(text); } catch (e) { throw new Error(`${label}: JSON không hợp lệ (${e.message})`); }
    if (!Array.isArray(v)) throw new Error(`${label}: phải là danh sách [ ... ]`);
    return v;
  }

  function openForm(rule) {
    editing = rule ? rule.id : null;
    f.title.textContent = rule ? "Sửa luật" : "Thêm luật";
    f.error.hidden = true;
    f.device.innerHTML = devices.map((d) => `<option value="${esc(d.key)}">${esc(d.key)} — ${esc(d.name)}</option>`).join("");
    const t = rule?.trigger || {};
    f.id.value = rule?.id || "";
    f.id.disabled = !!rule;                       // không đổi mã luật khi sửa
    f.name.value = rule?.name || "";
    f.desc.value = rule?.description || "";
    setKind(t.at ? "at" : "device");
    f.device.value = t.device || devices[0]?.key || "";
    f.field.value = t.field || "";
    f.op.value = t.op || "==";
    f.value.value = t.value === undefined ? "" : String(t.value);
    f.for.value = t.for || "";
    f.at.value = t.at || "";
    f.conds.value = pretty(rule?.conditions);
    f.actions.value = pretty(rule?.actions);
    f.cooldown.value = rule?.cooldown || "";
    f.enabled.checked = rule ? rule.enabled !== false : true;
    f.dialog.showModal();
    (rule ? f.name : f.id).focus();
  }

  function collect() {
    const trigger = kind === "at"
      ? { at: f.at.value }
      : { device: f.device.value, field: f.field.value.trim(), op: f.op.value, value: parseValue(f.value.value),
          ...(Number(f.for.value) > 0 ? { for: Number(f.for.value) } : {}) };
    return {
      id: f.id.value.trim(),
      name: f.name.value.trim(),
      description: f.desc.value.trim(),
      enabled: f.enabled.checked,
      trigger,
      conditions: parseJsonList(f.conds.value, "Điều kiện phụ"),
      actions: parseJsonList(f.actions.value, "Hành động"),
      ...(Number(f.cooldown.value) > 0 ? { cooldown: Number(f.cooldown.value) } : {}),
    };
  }

  $("ruleForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    f.error.hidden = true;
    $("ruleSubmit").disabled = true;
    try {
      const body = collect();
      if (editing) await call(`/api/admin/rules/${encodeURIComponent(editing)}`, "PUT", body);
      else await call("/api/admin/rules", "POST", body);
      f.dialog.close();
      toast(editing ? `Đã lưu luật “${body.name}”` : `Đã thêm luật “${body.name}”`);
      await load();
    } catch (err) {
      f.error.textContent = err.message;
      f.error.hidden = false;
      f.error.scrollIntoView({ block: "nearest" });
    }
    $("ruleSubmit").disabled = false;
  });

  $("btnAddRule").addEventListener("click", () => openForm(null));

  document.getElementById("admin-rules").addEventListener("click", async (e) => {
    const edit = e.target.closest("[data-edit]");
    const del = e.target.closest("[data-del]");
    const tog = e.target.closest("[data-toggle]");
    if (edit) openForm(rules.find((r) => r.id === edit.dataset.edit));
    if (tog) {
      const rule = rules.find((r) => r.id === tog.dataset.toggle);
      const enabled = rule.enabled === false;
      try {
        await call(`/api/admin/rules/${encodeURIComponent(rule.id)}/enabled`, "PUT", { enabled });
        toast(`${enabled ? "Đã bật" : "Đã tắt"} luật “${rule.name}”`);
        await load();
      } catch (err) { toast(err.message, "bad"); }
    }
    if (del) {
      const rule = rules.find((r) => r.id === del.dataset.del);
      if (!rule || !(await Admin.confirm({ title: "Xóa luật tự động", kind: "danger", ok: "Xóa",
        message: `Xóa luật “${rule.name}”? Automation sẽ ngừng chạy luật này ngay.` }))) return;
      try {
        await call(`/api/admin/rules/${encodeURIComponent(rule.id)}`, "DELETE");
        toast(`Đã xóa luật “${rule.name}”`);
        await load();
        } catch (err) { toast(err.message, "bad"); }
    }
  });

  // Mỗi lần mở trang thì tải lại (danh sách thiết bị có thể vừa đổi ở trang Thiết bị)
  document.addEventListener("admin:page", (e) => { if (e.detail === "rules") load(); });
})();
