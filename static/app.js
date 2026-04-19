(function () {
  const state = window.__TRAVEL_RADAR__;
  if (!state) {
    return;
  }

  const topicsBySlug = Object.fromEntries(state.topics.map((topic) => [topic.slug, topic]));
  const demoBySlug = Object.fromEntries(state.demoArticles.map((article) => [article.slug, article]));
  const runtime = state.runtimeConfig || {};
  const endpointMap = {
    ranking: "https://openapi.rakuten.co.jp/engine/api/Travel/HotelRanking/20170426",
    keyword: "https://openapi.rakuten.co.jp/engine/api/Travel/KeywordHotelSearch/20170426",
    vacant: "https://openapi.rakuten.co.jp/engine/api/Travel/VacantHotelSearch/20170426",
  };

  document.querySelectorAll("[data-topic-slug]").forEach((page) => {
    hydrateTopicPage(page.dataset.topicSlug, page).catch((error) => {
      console.error(error);
    });
  });

  async function hydrateTopicPage(slug, page) {
    const topic = topicsBySlug[slug];
    const demoArticle = demoBySlug[slug];
    if (!topic) {
      return;
    }

    if (!runtime.is_configured && demoArticle) {
      renderArticle(page, demoArticle, "demo", "楽天のWebアプリ設定前のため、デモデータを表示しています。");
      return;
    }

    setStatus(page, "最新データを読み込んでいます。", "ランキングと空室確認を順番に取得しています。");
    setLoadingCard(page, "楽天トラベルAPIに接続中です。");

    try {
      const liveArticle = await loadLiveArticle(topic);
      renderArticle(page, liveArticle, "live", "最新の空室候補を取得しました。");
    } catch (error) {
      if (demoArticle) {
        renderArticle(
          page,
          demoArticle,
          "fallback",
          "ライブ取得に失敗したため、デモデータを表示しています。"
        );
        setStatus(page, "ライブ取得に失敗しました。", normalizeError(error));
        return;
      }
      setStatus(page, "ライブ取得に失敗しました。", normalizeError(error));
      setLoadingCard(page, "データを取得できませんでした。時間をおいて再読み込みしてください。");
    }
  }

  async function loadLiveArticle(topic) {
    const today = getJstToday();
    const stay = determineStayDates(today, topic.stay_strategy);
    const cacheKey = [
      "travel-radar",
      topic.slug,
      stay.checkinDate,
      runtime.applicationId,
    ].join(":");
    const cached = readCache(cacheKey);
    if (cached) {
      return cached;
    }

    const seeds = await fetchSeedNodes(topic);
    const selected = [];

    for (let index = 0; index < seeds.length; index += 1) {
      const record = normalizeHotelRecord(seeds[index], index + 1);
      if (!record || !record.hotel_no) {
        continue;
      }

      let vacantPayload;
      try {
        vacantPayload = await requestJsonp(endpointMap.vacant, {
          carrier: 0,
          hotelNo: record.hotel_no,
          checkinDate: stay.checkinDate,
          checkoutDate: stay.checkoutDate,
          adultNum: topic.adult_num,
          childNum: topic.child_num || undefined,
          responseType: "large",
          sort: "+roomCharge",
          squeezeCondition: (topic.squeeze_conditions || []).join(",") || undefined,
        });
      } catch (error) {
        continue;
      }

      const vacantNodes = extractHotelNodes(vacantPayload);
      if (!vacantNodes.length) {
        continue;
      }

      const merged = mergeRecords(record, normalizeHotelRecord(vacantNodes[0], index + 1));
      if (!merged.booking_url) {
        continue;
      }
      merged.score = computeTopicScore(merged, topic);
      merged.selection_reason = buildSelectionReason(merged, topic, stay.checkinDate);
      selected.push(merged);
    }

    selected.sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return (left.displayed_charge || 999999) - (right.displayed_charge || 999999);
    });

    const hotels = selected.slice(0, topic.top_n);
    if (!hotels.length) {
      throw new Error("この条件では空室候補が見つかりませんでした。");
    }

    const article = {
      slug: topic.slug,
      title: renderTitleTemplate(topic.title_template, stay.checkinDate, stay.checkoutDate),
      headline: topic.headline,
      description:
        `${formatMonthDay(stay.checkinDate)}チェックインで空室を確認できた` +
        `${topic.headline}を楽天トラベルAPIから表示しています。`,
      topic_description: topic.description,
      checkin_date: stay.checkinDate,
      checkout_date: stay.checkoutDate,
      adult_num: topic.adult_num,
      child_num: topic.child_num,
      focus_label: topic.focus_label,
      generated_at: new Date().toISOString(),
      notes: [
        `空室と料金は ${formatJpDateTime(new Date())} JST 頃に取得した結果です。`,
        "本ページはアフィリエイト広告を利用しています。",
        "予約前に楽天トラベルの最新情報を必ずご確認ください。",
      ],
      hotels: hotels,
    };

    writeCache(cacheKey, article);
    return article;
  }

  async function fetchSeedNodes(topic) {
    if (topic.source === "ranking") {
      const payload = await requestJsonp(endpointMap.ranking, {
        carrier: 0,
        genre: topic.ranking_genre,
      });
      const rankings = extractRankingNodes(payload);
      const hotels = [];
      rankings.forEach((ranking) => {
        if (
          topic.ranking_genre &&
          String(findFirstValue(ranking, "genre") || "") &&
          String(findFirstValue(ranking, "genre") || "") !== topic.ranking_genre
        ) {
          return;
        }
        hotels.push(...extractHotelNodes(ranking));
      });
      return uniqueSeedNodes(hotels, topic.max_candidates);
    }

    if (topic.source === "keyword") {
      const hotels = [];
      for (const keyword of topic.keywords || []) {
        const payload = await requestJsonp(endpointMap.keyword, {
          carrier: 0,
          keyword: keyword,
          hits: Math.min(topic.max_candidates || 6, 6),
        });
        hotels.push(...extractHotelNodes(payload));
      }
      return uniqueSeedNodes(hotels, topic.max_candidates);
    }

    throw new Error("未対応のトピック種別です。");
  }

  function requestJsonp(url, params) {
    const callbackName = "__travelRadarJsonp_" + Math.random().toString(36).slice(2);
    const query = new URLSearchParams();
    query.set("applicationId", runtime.applicationId);
    query.set("accessKey", runtime.accessKey);
    query.set("format", "json");
    query.set("formatVersion", "2");
    query.set("callback", callbackName);
    if (runtime.affiliateId) {
      query.set("affiliateId", runtime.affiliateId);
    }
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") {
        return;
      }
      query.set(key, String(value));
    });

    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      const timeout = window.setTimeout(() => {
        cleanup();
        reject(new Error("楽天APIの応答がタイムアウトしました。"));
      }, 15000);

      function cleanup() {
        window.clearTimeout(timeout);
        delete window[callbackName];
        script.remove();
      }

      window[callbackName] = (payload) => {
        cleanup();
        resolve(payload);
      };

      script.onerror = () => {
        cleanup();
        reject(new Error("楽天APIの読み込みに失敗しました。"));
      };
      script.src = `${url}?${query.toString()}`;
      document.body.appendChild(script);
    });
  }

  function extractRankingNodes(payload) {
    const rankings = [];

    walk(payload, (node) => {
      if (node && typeof node === "object" && !Array.isArray(node)) {
        const keys = Object.keys(node).map((key) => key.toLowerCase());
        if (keys.includes("genre") && keys.includes("hotels")) {
          rankings.push(node);
        }
      }
    });
    return rankings;
  }

  function extractHotelNodes(payload) {
    const hotels = [];

    walk(payload, (node) => {
      if (isHotelWrapper(node)) {
        hotels.push(node);
        return true;
      }
      return false;
    });
    return hotels;
  }

  function isHotelWrapper(node) {
    if (Array.isArray(node)) {
      return node.some(
        (item) =>
          item &&
          typeof item === "object" &&
          ["hotelBasicInfo", "hotelRatingInfo", "hotelDetailInfo", "hotelFacilitiesInfo"].some((key) =>
            Object.prototype.hasOwnProperty.call(item, key)
          )
      );
    }

    if (node && typeof node === "object") {
      const keys = Object.keys(node);
      if (
        ["hotelBasicInfo", "hotelRatingInfo", "hotelDetailInfo", "hotelFacilitiesInfo"].some((key) =>
          keys.includes(key)
        )
      ) {
        return true;
      }
      const lowered = keys.map((key) => key.toLowerCase());
      return lowered.includes("hotelno") && lowered.includes("hotelname");
    }
    return false;
  }

  function uniqueSeedNodes(nodes, maxItems) {
    const seen = new Set();
    const uniqueNodes = [];
    for (const node of nodes) {
      const hotelNo = String(findFirstValue(node, "hotelNo") || "").trim();
      if (!hotelNo || seen.has(hotelNo)) {
        continue;
      }
      seen.add(hotelNo);
      uniqueNodes.push(node);
      if (uniqueNodes.length >= maxItems) {
        break;
      }
    }
    return uniqueNodes;
  }

  function normalizeHotelRecord(rawHotel, seedRank) {
    const hotelNo = String(findFirstValue(rawHotel, "hotelNo") || "").trim();
    const hotelName = collapseWhitespace(String(findFirstValue(rawHotel, "hotelName") || ""));
    if (!hotelNo || !hotelName) {
      return null;
    }

    const roomCharges = findAllValues(rawHotel, "roomCharge")
      .map((value) => coerceInt(value))
      .filter((value) => value);

    const address = [
      collapseWhitespace(String(findFirstValue(rawHotel, "address1") || "")),
      collapseWhitespace(String(findFirstValue(rawHotel, "address2") || "")),
    ]
      .filter(Boolean)
      .join(" ");

    const record = {
      hotel_no: hotelNo,
      name: hotelName,
      area_name: collapseWhitespace(
        String(findFirstValue(rawHotel, "areaName", "middleClassName") || "")
      ),
      address: address,
      access: collapseWhitespace(String(findFirstValue(rawHotel, "access") || "")),
      nearest_station: collapseWhitespace(String(findFirstValue(rawHotel, "nearestStation") || "")),
      special: shortenText(
        collapseWhitespace(
          String(findFirstValue(rawHotel, "hotelSpecial", "userReview", "otherInformation") || "")
        ),
        150
      ),
      review_average: coerceFloat(findFirstValue(rawHotel, "reviewAverage")),
      review_count: coerceInt(findFirstValue(rawHotel, "reviewCount")),
      meal_average: coerceFloat(findFirstValue(rawHotel, "mealAverage")),
      bath_average: coerceFloat(findFirstValue(rawHotel, "bathAverage")),
      room_average: coerceFloat(findFirstValue(rawHotel, "roomAverage")),
      service_average: coerceFloat(findFirstValue(rawHotel, "serviceAverage")),
      min_charge: coerceInt(findFirstValue(rawHotel, "hotelMinCharge")),
      room_charge: roomCharges.length ? Math.min.apply(null, roomCharges) : null,
      hotel_information_url: String(findFirstValue(rawHotel, "hotelInformationUrl") || ""),
      plan_list_url: String(findFirstValue(rawHotel, "planListUrl") || ""),
      check_available_url: String(findFirstValue(rawHotel, "checkAvailableUrl") || ""),
      review_url: String(findFirstValue(rawHotel, "reviewUrl") || ""),
      image_url: String(
        findFirstValue(
          rawHotel,
          "hotelImageUrl",
          "hotelThumbnailUrl",
          "roomImageUrl",
          "roomThumbnailUrl"
        ) || ""
      ),
      selection_reason: "",
      score: 0,
      seed_rank: seedRank,
      raw: rawHotel,
    };
    record.booking_url =
      record.hotel_information_url ||
      record.plan_list_url ||
      record.check_available_url ||
      record.review_url ||
      "";
    record.displayed_charge = record.room_charge || record.min_charge || null;
    return record;
  }

  function mergeRecords(base, update) {
    if (!base) {
      return update;
    }
    if (!update) {
      return base;
    }
    const merged = {};
    Object.keys(base).forEach((key) => {
      merged[key] = isPresent(update[key]) ? update[key] : base[key];
    });
    merged.booking_url =
      merged.hotel_information_url ||
      merged.plan_list_url ||
      merged.check_available_url ||
      merged.review_url ||
      "";
    merged.displayed_charge = merged.room_charge || merged.min_charge || null;
    return merged;
  }

  function computeTopicScore(record, topic) {
    const focusValue = record[topic.focus_metric] || 0;
    const reviewAverage = record.review_average || 0;
    const reviewCount = record.review_count || 0;
    const displayedCharge = record.displayed_charge || 25000;
    const seedRank = record.seed_rank || topic.max_candidates;
    let score = 0;
    score += Math.max(0, 12 - seedRank) * 2.5;
    score += reviewAverage * 8;
    score += focusValue * 10;
    score += Math.min(reviewCount, 400) / 30;
    score += Math.max(0, 25000 - Math.min(displayedCharge, 25000)) / 2500;
    if (topic.focus_min && focusValue < topic.focus_min) {
      score -= 12;
    }
    if (topic.source === "keyword") {
      const haystack = [record.name, record.special, record.area_name].join(" ");
      (topic.keywords || []).forEach((keyword) => {
        if (keyword && haystack.includes(keyword)) {
          score += 2;
        }
      });
    }
    return Number(score.toFixed(2));
  }

  function buildSelectionReason(record, topic, checkinDate) {
    const parts = [];
    const focusValue = record[topic.focus_metric];
    if (focusValue) {
      parts.push(`${topic.focus_label}${focusValue.toFixed(1)}`);
    }
    if (record.review_average && topic.focus_metric !== "review_average") {
      parts.push(`総合${record.review_average.toFixed(1)}`);
    }
    if (record.review_count) {
      parts.push(`口コミ${record.review_count}件`);
    }
    if (record.displayed_charge) {
      parts.push(`${formatMonthDay(checkinDate)}時点で${numberFormat(record.displayed_charge)}円前後から`);
    }
    if (record.nearest_station) {
      parts.push(`${record.nearest_station}アクセス`);
    }
    return parts.slice(0, 4).join(" / ") || "空室確認が取れた宿です。";
  }

  function determineStayDates(today, stayStrategy) {
    const weekdayMap = {
      next_friday: 5,
      next_saturday: 6,
    };
    const targetWeekday = weekdayMap[stayStrategy] || 6;
    const currentWeekday = today.getUTCDay();
    let daysAhead = (targetWeekday - currentWeekday + 7) % 7;
    if (daysAhead === 0) {
      daysAhead = 7;
    }
    const checkin = addDays(today, daysAhead);
    const checkout = addDays(checkin, 1);
    return {
      checkinDate: toIsoDate(checkin),
      checkoutDate: toIsoDate(checkout),
    };
  }

  function renderArticle(page, article, mode, statusMessage) {
    const titleElement = page.querySelector("[data-article-title]");
    const descriptionElement = page.querySelector("[data-article-description]");
    const conditionsElement = page.querySelector("[data-article-conditions]");
    const resultsElement = page.querySelector("[data-results]");
    const notesElement = page.querySelector("[data-notes]");

    if (titleElement) {
      titleElement.textContent = article.title;
    }
    if (descriptionElement) {
      descriptionElement.textContent = article.description;
    }
    if (conditionsElement) {
      const conditions = [
        `チェックイン ${formatIsoAsJp(article.checkin_date)}`,
        `チェックアウト ${formatIsoAsJp(article.checkout_date)}`,
        `大人${article.adult_num}名`,
      ];
      if (article.child_num) {
        conditions.push(`子ども${article.child_num}名`);
      }
      conditionsElement.innerHTML = conditions.map((item) => `<span>${escapeHtml(item)}</span>`).join("");
    }
    if (resultsElement) {
      resultsElement.innerHTML = article.hotels
        .map((hotel, index) => renderHotelCard(hotel, index + 1, article.focus_label))
        .join("");
    }
    if (notesElement) {
      notesElement.innerHTML = article.notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("");
    }

    const modeText =
      mode === "live"
        ? "ライブ表示"
        : mode === "demo"
          ? "デモ表示"
          : "フォールバック表示";
    setStatus(page, statusMessage, `${modeText} / ${article.hotels.length}件表示`);
    document.title = article.title;
  }

  function renderHotelCard(hotel, rank, focusLabel) {
    const badges = [];
    if (hotel.review_average) {
      badges.push(metricBadge("総合", hotel.review_average.toFixed(1)));
    }
    const focusValue = pickFocusValue(hotel, focusLabel);
    if (focusValue) {
      badges.push(metricBadge(focusLabel, focusValue.toFixed(1)));
    }
    if (hotel.displayed_charge) {
      badges.push(metricBadge("料金目安", `${numberFormat(hotel.displayed_charge)}円〜`));
    }
    const imageHtml = hotel.image_url
      ? `<img src="${escapeAttribute(hotel.image_url)}" alt="${escapeAttribute(hotel.name)}のイメージ"/>`
      : '<div class="image-fallback">No Image</div>';
    const accessText = hotel.access || hotel.address || "";
    return `
<article class="hotel-card">
  <div class="hotel-media">
    <span class="rank-badge">#${rank}</span>
    ${imageHtml}
  </div>
  <div class="hotel-content">
    <p class="eyebrow">${escapeHtml(hotel.area_name || "Rakuten Travel")}</p>
    <h3>${escapeHtml(hotel.name)}</h3>
    <div class="badge-row">${badges.join("")}</div>
    <p class="selection-reason">${escapeHtml(hotel.selection_reason || "")}</p>
    <p>${escapeHtml(hotel.special || "詳細は予約ページでご確認ください。")}</p>
    ${accessText ? `<div class="hotel-meta"><p>${escapeHtml(accessText)}</p></div>` : ""}
    <a class="primary-link" href="${escapeAttribute(hotel.booking_url)}" target="_blank" rel="noopener noreferrer">楽天トラベルで確認</a>
  </div>
</article>`;
  }

  function setStatus(page, message, subMessage) {
    const messageElement = page.querySelector("[data-status-message]");
    const subElement = page.querySelector("[data-status-sub]");
    if (messageElement) {
      messageElement.textContent = message;
    }
    if (subElement) {
      subElement.textContent = subMessage;
    }
  }

  function setLoadingCard(page, message) {
    const resultsElement = page.querySelector("[data-results]");
    if (!resultsElement) {
      return;
    }
    resultsElement.innerHTML = `
<article class="panel loading-card">
  <h3>読み込み中</h3>
  <p>${escapeHtml(message)}</p>
</article>`;
  }

  function pickFocusValue(hotel, focusLabel) {
    if (focusLabel === "食事評価") {
      return hotel.meal_average;
    }
    if (focusLabel === "風呂評価") {
      return hotel.bath_average;
    }
    return hotel.review_average;
  }

  function readCache(key) {
    try {
      const raw = window.localStorage.getItem(key);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      if (Date.now() - parsed.timestamp > 30 * 60 * 1000) {
        return null;
      }
      return parsed.value;
    } catch (error) {
      return null;
    }
  }

  function writeCache(key, value) {
    try {
      window.localStorage.setItem(
        key,
        JSON.stringify({
          timestamp: Date.now(),
          value: value,
        })
      );
    } catch (error) {
      return;
    }
  }

  function findFirstValue(node) {
    const keys = Array.prototype.slice.call(arguments, 1).map((key) => String(key).toLowerCase());

    function search(value) {
      if (Array.isArray(value)) {
        for (const child of value) {
          const found = search(child);
          if (isPresent(found)) {
            return found;
          }
        }
        return null;
      }
      if (value && typeof value === "object") {
        for (const [key, child] of Object.entries(value)) {
          if (keys.includes(key.toLowerCase()) && isPresent(child)) {
            return child;
          }
        }
        for (const child of Object.values(value)) {
          const found = search(child);
          if (isPresent(found)) {
            return found;
          }
        }
      }
      return null;
    }

    return search(node);
  }

  function findAllValues(node, keyName) {
    const values = [];
    const lowered = String(keyName).toLowerCase();
    walk(node, (value) => {
      if (value && typeof value === "object" && !Array.isArray(value)) {
        Object.entries(value).forEach(([key, child]) => {
          if (key.toLowerCase() === lowered && isPresent(child)) {
            values.push(child);
          }
        });
      }
      return false;
    });
    return values;
  }

  function walk(node, visitor) {
    if (visitor(node) === true) {
      return true;
    }
    if (Array.isArray(node)) {
      for (const item of node) {
        if (walk(item, visitor) === true) {
          return true;
        }
      }
      return false;
    }
    if (node && typeof node === "object") {
      for (const child of Object.values(node)) {
        if (walk(child, visitor) === true) {
          return true;
        }
      }
    }
    return false;
  }

  function coerceFloat(value) {
    if (!isPresent(value)) {
      return null;
    }
    const parsed = Number(String(value).replace(/,/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  }

  function coerceInt(value) {
    if (!isPresent(value)) {
      return null;
    }
    const parsed = Number(String(value).replace(/,/g, ""));
    return Number.isFinite(parsed) ? Math.round(parsed) : null;
  }

  function isPresent(value) {
    return value !== null && value !== undefined && value !== "" && !(Array.isArray(value) && !value.length);
  }

  function collapseWhitespace(text) {
    return String(text).trim().replace(/\s+/g, " ");
  }

  function shortenText(text, maxLength) {
    if (text.length <= maxLength) {
      return text;
    }
    return text.slice(0, maxLength - 1).trimEnd() + "…";
  }

  function renderTitleTemplate(template, checkinDate, checkoutDate) {
    const date = parseIsoDate(checkinDate);
    return template
      .replaceAll("{checkin_md}", formatMonthDay(checkinDate))
      .replaceAll("{month}", String(date.getUTCMonth() + 1))
      .replaceAll("{month_label}", `${date.getUTCMonth() + 1}月`)
      .replaceAll("{checkin_date}", checkinDate)
      .replaceAll("{checkout_date}", checkoutDate || "");
  }

  function getJstToday() {
    const formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Tokyo",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    const parts = Object.fromEntries(
      formatter
        .formatToParts(new Date())
        .filter((part) => part.type !== "literal")
        .map((part) => [part.type, part.value])
    );
    return parseIsoDate(`${parts.year}-${parts.month}-${parts.day}`);
  }

  function addDays(date, count) {
    const next = new Date(date.getTime());
    next.setUTCDate(next.getUTCDate() + count);
    return next;
  }

  function parseIsoDate(value) {
    const parts = String(value).split("-").map((part) => Number(part));
    return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
  }

  function toIsoDate(date) {
    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    const day = String(date.getUTCDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function formatMonthDay(value) {
    const date = typeof value === "string" ? parseIsoDate(value) : value;
    return `${date.getUTCMonth() + 1}/${date.getUTCDate()}`;
  }

  function formatIsoAsJp(value) {
    const date = parseIsoDate(value);
    return `${date.getUTCFullYear()}年${date.getUTCMonth() + 1}月${date.getUTCDate()}日`;
  }

  function formatJpDateTime(date) {
    const formatter = new Intl.DateTimeFormat("ja-JP", {
      timeZone: "Asia/Tokyo",
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
    return formatter.format(date);
  }

  function numberFormat(value) {
    return new Intl.NumberFormat("ja-JP").format(value);
  }

  function metricBadge(label, value) {
    return `<span class="metric-badge">${escapeHtml(label)} ${escapeHtml(value)}</span>`;
  }

  function normalizeError(error) {
    return error && error.message ? error.message : "不明なエラーが発生しました。";
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function escapeAttribute(value) {
    return escapeHtml(value);
  }
})();
