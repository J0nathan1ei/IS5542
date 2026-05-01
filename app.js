const state = {
  products: [],
  filtered: [],
  gender: "All",
  season: "All",
  search: "",
  bag: [],
};

const grid = document.querySelector("#productGrid");
const resultCount = document.querySelector("#resultCount");
const seasonSelect = document.querySelector("#seasonSelect");
const searchInput = document.querySelector("#searchInput");
const resetFilters = document.querySelector("#resetFilters");
const genderFilters = document.querySelector("#genderFilters");
const quickView = document.querySelector("#quickView");
const quickViewContent = document.querySelector("#quickViewContent");
const closeQuickView = document.querySelector("#closeQuickView");
const bagDrawer = document.querySelector("#bagDrawer");
const bagButton = document.querySelector("#bagButton");
const closeBag = document.querySelector("#closeBag");
const bagItems = document.querySelector("#bagItems");
const bagTotal = document.querySelector("#bagTotal");
const bagCount = document.querySelector("#bagCount");

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (char === '"' && quoted && next === '"') {
      cell += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") i += 1;
      row.push(cell);
      if (row.some((value) => value.trim() !== "")) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }

  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }

  const headers = rows.shift();
  return rows.map((values) =>
    headers.reduce((product, header, index) => {
      product[header] = values[index] || "";
      return product;
    }, {})
  );
}

function normaliseProduct(product) {
  const id = product["Product ID"];
  return {
    id,
    name: product["Product Name"],
    category: product.Category,
    gender: product.Gender,
    season: product.Season,
    style: product.Style,
    occasion: product.Occasion,
    color: product.Color,
    material: product.Material,
    price: product.Price,
    amount: Number(product.Price.replace(/[^\d.]/g, "")),
    sizes: product.Sizes,
    description: product.Description,
    matching: product["Matching Suggestions"],
    image: `pic/${id}.jpg`,
  };
}

function productMatches(product) {
  const search = state.search.toLowerCase();
  const searchable = [
    product.name,
    product.category,
    product.gender,
    product.season,
    product.style,
    product.occasion,
    product.color,
    product.material,
  ]
    .join(" ")
    .toLowerCase();

  return (
    (state.gender === "All" || product.gender === state.gender) &&
    (state.season === "All" || product.season.includes(state.season)) &&
    (!search || searchable.includes(search))
  );
}

function renderProducts() {
  state.filtered = state.products.filter(productMatches);
  resultCount.textContent = `${state.filtered.length} styles available`;
  grid.innerHTML = state.filtered
    .slice(0, 32)
    .map(
      (product) => `
        <article class="product-card">
          <div class="product-image-wrap">
            <img src="${product.image}" alt="${product.name}" loading="lazy" />
            <span class="pill">${product.gender === "Female" ? "Women" : "Men"}</span>
            <button class="quick-button" type="button" data-view="${product.id}">Quick View</button>
          </div>
          <div class="product-info">
            <h3>${product.name}</h3>
            <span class="price">${product.price}</span>
            <span class="meta">${product.category} · ${product.color}</span>
            <span class="sizes">Sizes ${product.sizes}</span>
          </div>
        </article>
      `
    )
    .join("");
}

function renderSeasons() {
  const seasons = new Set();
  state.products.forEach((product) => {
    product.season.split("/").forEach((season) => seasons.add(season.trim()));
  });

  [...seasons].sort().forEach((season) => {
    const option = document.createElement("option");
    option.value = season;
    option.textContent = season;
    seasonSelect.append(option);
  });
}

function openQuickView(product) {
  quickViewContent.innerHTML = `
    <div class="quick-layout">
      <img src="${product.image}" alt="${product.name}" />
      <div class="quick-copy">
        <p class="eyebrow">${product.gender === "Female" ? "Women" : "Men"} · ${product.category}</p>
        <h2>${product.name}</h2>
        <strong class="price">${product.price}</strong>
        <p>${product.description}</p>
        <div class="detail-list">
          <span>Style: ${product.style}</span>
          <span>Occasion: ${product.occasion}</span>
          <span>Material: ${product.material}</span>
          <span>Sizes: ${product.sizes}</span>
        </div>
        <p>${product.matching}</p>
        <button class="add-button" type="button" data-add="${product.id}">Add To Bag</button>
      </div>
    </div>
  `;
  quickView.showModal();
}

function renderBag() {
  bagCount.textContent = state.bag.length;
  if (!state.bag.length) {
    bagItems.innerHTML = "<p>Your preview bag is empty.</p>";
    bagTotal.textContent = "HKD 0";
    return;
  }

  bagItems.innerHTML = state.bag
    .map(
      (product) => `
        <article class="bag-item">
          <img src="${product.image}" alt="${product.name}" />
          <div>
            <h3>${product.name}</h3>
            <p>${product.price}</p>
            <p>${product.category} · ${product.color}</p>
          </div>
        </article>
      `
    )
    .join("");

  const total = state.bag.reduce((sum, product) => sum + product.amount, 0);
  bagTotal.textContent = `HKD ${total.toLocaleString("en-HK")}`;
}

function addToBag(product) {
  state.bag.push(product);
  renderBag();
  bagDrawer.classList.add("open");
  bagDrawer.setAttribute("aria-hidden", "false");
}

function resetAllFilters() {
  state.gender = "All";
  state.season = "All";
  state.search = "";
  searchInput.value = "";
  seasonSelect.value = "All";
  genderFilters.querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.dataset.value === "All");
  });
  renderProducts();
}

genderFilters.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  state.gender = button.dataset.value;
  genderFilters.querySelectorAll("button").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  renderProducts();
});

seasonSelect.addEventListener("change", (event) => {
  state.season = event.target.value;
  renderProducts();
});

searchInput.addEventListener("input", (event) => {
  state.search = event.target.value.trim();
  renderProducts();
});

resetFilters.addEventListener("click", resetAllFilters);

grid.addEventListener("click", (event) => {
  const button = event.target.closest("[data-view]");
  if (!button) return;
  const product = state.products.find((item) => item.id === button.dataset.view);
  if (product) openQuickView(product);
});

quickViewContent.addEventListener("click", (event) => {
  const button = event.target.closest("[data-add]");
  if (!button) return;
  const product = state.products.find((item) => item.id === button.dataset.add);
  if (product) addToBag(product);
});

closeQuickView.addEventListener("click", () => quickView.close());

bagButton.addEventListener("click", () => {
  bagDrawer.classList.add("open");
  bagDrawer.setAttribute("aria-hidden", "false");
});

closeBag.addEventListener("click", () => {
  bagDrawer.classList.remove("open");
  bagDrawer.setAttribute("aria-hidden", "true");
});

bagDrawer.addEventListener("click", (event) => {
  if (event.target === bagDrawer) {
    bagDrawer.classList.remove("open");
    bagDrawer.setAttribute("aria-hidden", "true");
  }
});

async function init() {
  try {
    const response = await fetch("clothing_rag_dataset.csv");
    const csv = await response.text();
    state.products = parseCsv(csv).map(normaliseProduct);
    renderSeasons();
    renderProducts();
    renderBag();
  } catch (error) {
    resultCount.textContent = "Unable to load the collection.";
    grid.innerHTML = `<p>Please open this site through a local server or GitHub Pages.</p>`;
  }
}

init();
