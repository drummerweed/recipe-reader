document.addEventListener('DOMContentLoaded', () => {
    // Views
    const viewScrape = document.getElementById('view-scrape');
    const viewLibrary = document.getElementById('view-library');
    const viewPantry = document.getElementById('view-pantry');
    const viewReader = document.getElementById('view-reader');
    
    // Nav
    const navBtnLibrary = document.getElementById('nav-btn-library');
    const navBtnPantry = document.getElementById('nav-btn-pantry');
    const navBtnNew = document.getElementById('nav-btn-new');
    const navHome = document.getElementById('nav-home');

    // Scrape Form
    const form = document.getElementById('scrape-form');
    const urlInput = document.getElementById('url-input');
    const submitBtn = document.getElementById('submit-btn');
    const errorMsg = document.getElementById('error-message');
    const loading = document.getElementById('loading');
    
    // Dropdown
    const actionMenuBtn = document.getElementById('action-menu-btn');
    const actionMenu = document.querySelector('.dropdown-menu');
    const actionSave = document.getElementById('action-save');
    const actionPrint = document.getElementById('action-print');
    const actionSource = document.getElementById('action-source');
    const actionDelete = document.getElementById('action-delete');

    // Reader Elements
    const elCategory = document.getElementById('recipe-category');
    const elCategorySavedMsg = document.getElementById('category-saved-msg');
    const elTitle = document.getElementById('recipe-title');
    const elDesc = document.getElementById('recipe-description');
    const elSysImageContainer = document.getElementById('recipe-image-container');
    const elImage = document.getElementById('recipe-image');
    const elYields = document.getElementById('recipe-yields');
    const elPrep = document.getElementById('recipe-prep');
    const elCook = document.getElementById('recipe-cook');
    const elTotal = document.getElementById('recipe-total');
    
    const wrapYields = document.getElementById('meta-yields-container');
    const wrapPrep = document.getElementById('meta-prep-container');
    const wrapCook = document.getElementById('meta-cook-container');
    const wrapTotal = document.getElementById('meta-total-container');
    
    const listIngredients = document.getElementById('recipe-ingredients');
    const listInstructions = document.getElementById('recipe-instructions');
    const btnConvertUnits = document.getElementById('convert-units-btn');

    // Library
    const libraryEmpty = document.getElementById('library-empty');
    const libraryContent = document.getElementById('library-content');
    const librarySearchInput = document.getElementById('library-search-input');

    // State
    let currentScrapedRecipe = null;
    let currentViewedId = null; 
    let currentOriginalIngredients = [];
    let unitState = 'original'; // 'original', 'metric', 'imperial'

    // --- NAVIGATION ---
    function showView(view) {
        viewScrape.classList.add('hidden');
        viewLibrary.classList.add('hidden');
        viewPantry.classList.add('hidden');
        viewReader.classList.add('hidden');
        view.classList.remove('hidden');
    }

    navBtnNew.addEventListener('click', () => {
        urlInput.value = '';
        errorMsg.textContent = '';
        errorMsg.classList.add('hidden');
        showView(viewScrape);
    });
    navHome.addEventListener('click', () => {
        urlInput.value = '';
        errorMsg.textContent = '';
        errorMsg.classList.add('hidden');
        showView(viewScrape);
    });
    navBtnLibrary.addEventListener('click', () => {
        librarySearchInput.value = '';
        loadLibrary();
    });
    navBtnPantry.addEventListener('click', () => { showView(viewPantry); loadPantryCloud(); });

    // --- DROPDOWN ---
    actionMenuBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        actionMenu.classList.toggle('show');
    });

    document.addEventListener('click', (e) => {
        if (!actionMenuBtn.contains(e.target) && !actionMenu.contains(e.target)) {
            actionMenu.classList.remove('show');
        }
    });

    actionPrint.addEventListener('click', () => {
        actionMenu.classList.remove('show');
        window.print();
    });

    // --- SCRAPING ---
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const url = urlInput.value.trim();
        if (!url) return;
        
        errorMsg.textContent = '';
        errorMsg.classList.add('hidden');
        loading.classList.remove('hidden');
        submitBtn.disabled = true;

        try {
            const response = await fetch('/api/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || "Failed to extract recipe.");
            }
            
            currentScrapedRecipe = data;
            currentViewedId = null; // not saved yet
            populateRecipeReader(data);
            
            // Show save button
            actionSave.style.display = 'block';
            actionSave.textContent = '💾 Save to Library';
            actionSave.disabled = false;

            loading.classList.add('hidden');
            actionDelete.classList.add('hidden');
            showView(viewReader);
            
        } catch (err) {
            loading.classList.add('hidden');
            errorMsg.textContent = err.message;
            errorMsg.classList.remove('hidden');
        } finally {
            submitBtn.disabled = false;
        }
    });

    
    // --- PANTRY ---
    const pantryInput = document.getElementById('pantry-input');
    const pantryTags = document.getElementById('pantry-tags');
    const pantrySearchBtn = document.getElementById('pantry-search-btn');
    const pantryLoading = document.getElementById('pantry-loading');
    const pantryError = document.getElementById('pantry-error');
    const pantryResults = document.getElementById('pantry-results');
    const pantryEmpty = document.getElementById('pantry-empty');
    let pantryItems = [];

    const pantryCloud = document.getElementById('pantry-cloud');
    
    async function loadPantryCloud() {
        try {
            const res = await fetch('/api/pantry/cloud');
            const data = await res.json();
            
            pantryCloud.innerHTML = '';
            if (data.success && data.cloud.length > 0) {
                data.cloud.forEach(word => {
                    const pill = document.createElement('div');
                    pill.className = 'pantry-pill';
                    pill.innerHTML = `<span>${word}</span> <span style="font-size: 0.8rem; opacity:0.5;">+</span>`;
                    
                    pill.addEventListener('click', () => {
                        if (!pantryItems.includes(word)) {
                            pantryItems.push(word);
                            renderPantryTags();
                        }
                    });
                    
                    pantryCloud.appendChild(pill);
                });
            } else {
                pantryCloud.innerHTML = '<span style="color:var(--text-secondary);font-size:0.9rem;">No common ingredients yet! Add recipes to build your cloud.</span>';
            }
        } catch (err) {
            console.error("Cloud Error:", err);
        }
    }


    const pantrySuggestions = document.getElementById('pantry-suggestions');
    let suggestTimeout = null;

    pantryInput.addEventListener('input', (e) => {
        const val = e.target.value.trim();
        if (val.length < 2) {
            pantrySuggestions.classList.add('hidden');
            return;
        }

        clearTimeout(suggestTimeout);
        suggestTimeout = setTimeout(async () => {
            try {
                const res = await fetch(`/api/pantry/suggest?q=${encodeURIComponent(val)}`);
                const data = await res.json();
                
                if (data.success && data.suggestions.length > 0) {
                    pantrySuggestions.innerHTML = '';
                    data.suggestions.forEach(sug => {
                        const li = document.createElement('li');
                        li.className = 'suggestion-item';
                        li.textContent = sug;
                        li.addEventListener('click', () => {
                            if (!pantryItems.includes(sug)) {
                                pantryItems.push(sug);
                                renderPantryTags();
                            }
                            pantryInput.value = '';
                            pantrySuggestions.classList.add('hidden');
                            pantryInput.focus();
                        });
                        pantrySuggestions.appendChild(li);
                    });
                    pantrySuggestions.classList.remove('hidden');
                } else {
                    pantrySuggestions.classList.add('hidden');
                }
            } catch (err) {
                console.error("Suggestion error:", err);
            }
        }, 150); // Small debounce
    });

    // Close suggestions if clicking elsewhere
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.google-search-container')) {
            pantrySuggestions.classList.add('hidden');
        }
    });


    function renderPantryTags() {
        pantryTags.innerHTML = '';
        pantryItems.forEach((item, index) => {
            const pill = document.createElement('div');
            pill.className = 'pantry-pill';
            pill.innerHTML = `<span>${item}</span><div class="pill-remove" data-index="${index}">✕</div>`;
            pantryTags.appendChild(pill);
        });
        
        document.querySelectorAll('.pill-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = e.target.getAttribute('data-index');
                pantryItems.splice(idx, 1);
                renderPantryTags();
            });
        });
    }

    pantryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            const val = pantryInput.value.trim();
            if (val && !pantryItems.includes(val)) {
                pantryItems.push(val);
                pantryInput.value = '';
                renderPantryTags();
            }
        }
    });

    pantrySearchBtn.addEventListener('click', async () => {
        if (pantryItems.length === 0) return;
        
        pantryError.classList.add('hidden');
        pantryEmpty.classList.add('hidden');
        pantryResults.innerHTML = '';
        pantryLoading.querySelector('p').textContent = 'Finding recipes with ' + pantryItems.join(', ') + '...';
        pantryLoading.classList.remove('hidden');
        pantrySearchBtn.disabled = true;

        try {
            const res = await fetch('/api/pantry/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pantry: pantryItems })
            });
            const data = await res.json();
            
            pantryLoading.classList.add('hidden');
            
            if (!data.success) throw new Error(data.error || "Unknown search error");
            
            if (data.results.length === 0) {
                pantryEmpty.querySelector('.empty-state').textContent = `No recipes match "${pantryItems.join(', ')}". Try adding more items!`;
                pantryEmpty.classList.remove('hidden');
            } else {
                pantryEmpty.classList.add('hidden');
                let html = '';
                data.results.forEach(r => {
                    const img = r.image ? `<img src="${r.image}" class="lib-image">` : `<div class="lib-image"></div>`;
                    const time = r.total_time ? `<div class="lib-time">⏱️ ${r.total_time}</div>` : '';
                    const badgeStr = r.missing_count === 0 ? 'Perfect match!' : `Missing ${r.missing_count}`;
                    const badgeClass = r.missing_count === 0 ? 'missing-badge perfect-match' : 'missing-badge';
                    
                    html += `
                        <a href="#" class="library-card" data-id="${r.id}">
                            <div class="${badgeClass}">${badgeStr}</div>
                            ${img}
                            <div class="lib-content">
                                <div class="lib-title">${r.title}</div>
                                ${time}
                            </div>
                        </a>
                    `;
                });
                pantryResults.innerHTML = html;
                
                // Add click events
                document.querySelectorAll('#pantry-results .library-card').forEach(card => {
                    card.addEventListener('click', (e) => {
                        e.preventDefault();
                        viewSavedRecipe(card.getAttribute('data-id'));
                    });
                });
            }
        } catch (err) {
            pantryLoading.classList.add('hidden');
            pantryError.textContent = err.message;
            pantryError.classList.remove('hidden');
        } finally {
            pantrySearchBtn.disabled = false;
        }
    });

    // --- SAVING ---
    actionSave.addEventListener('click', async () => {
        if (!currentScrapedRecipe) return;
        
        actionSave.textContent = 'Saving...';
        actionSave.disabled = true;

        try {
            const response = await fetch('/api/recipes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentScrapedRecipe)
            });
            
            const data = await response.json();
            if (data.success) {
                actionSave.textContent = '✅ Saved';
                currentViewedId = data.id;
            } else {
                throw new Error(data.error);
            }
        } catch(err) {
            alert('Error saving recipe: ' + err.message);
            actionSave.textContent = '💾 Save to Library';
            actionSave.disabled = false;
        }
    });

    // --- LIBRARY ---
    async function loadLibrary(q = '') {
        if (typeof q !== 'string') q = '';
        showView(viewLibrary);
        libraryEmpty.classList.add('hidden');
        libraryContent.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const url = q ? `/api/recipes?q=${encodeURIComponent(q)}` : '/api/recipes';
            const res = await fetch(url);
            const data = await res.json();

            let hasAny = false;
            let html = '';

            let tabsHtml = '<div class="library-tabs">';
            let contentHtml = '';
            let firstTab = true;

            const order = ["Breakfast", "Lunch", "Dinner", "Snacks"];
            order.forEach(cat => {
                const recipes = data.categories[cat];
                if (recipes && recipes.length > 0) {
                    hasAny = true;
                    
                    const activeClass = firstTab ? 'active' : '';
                    tabsHtml += `<button class="tab-btn ${activeClass}" data-tab="${cat}">${cat}</button>`;
                    
                    const hiddenClass = firstTab ? '' : 'hidden';
                    contentHtml += `
                        <div class="category-section tab-content ${hiddenClass}" id="tab-${cat}">
                            <div class="recipe-grid">
                    `;
                    recipes.forEach(r => {
                        const img = r.image ? `<img src="${r.image}" class="lib-image">` : `<div class="lib-image"></div>`;
                        const time = r.total_time ? `<div class="lib-time">⏱️ ${r.total_time}</div>` : '';
                        html += `
                            <a href="#" class="library-card" data-id="${r.id}">
                                ${img}
                                <div class="lib-content">
                                    <div class="lib-title">${r.title}</div>
                                    ${time}
                                </div>
                            </a>
                        `;
                    });
                    contentHtml += html;
                    html = ''; // clear for next tab
                    contentHtml += `</div></div>`;
                    
                    firstTab = false;
                }
            });
            tabsHtml += '</div>';

            if (!hasAny) {
                libraryContent.innerHTML = '';
                libraryEmpty.classList.remove('hidden');
                if (q) {
                    libraryEmpty.querySelector('.empty-state').textContent = `No recipes match "${q}".`;
                } else {
                    libraryEmpty.querySelector('.empty-state').textContent = "No recipes saved yet. Go add one!";
                }
            } else {
                libraryContent.innerHTML = tabsHtml + contentHtml;
                
                // Add click events to tabs
                document.querySelectorAll('.tab-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                        document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
                        
                        e.target.classList.add('active');
                        const targetTab = e.target.getAttribute('data-tab');
                        document.getElementById(`tab-${targetTab}`).classList.remove('hidden');
                    });
                });
                
                // Add click events to cards
                document.querySelectorAll('.library-card').forEach(card => {
                    card.addEventListener('click', (e) => {
                        e.preventDefault();
                        const id = card.getAttribute('data-id');
                        viewSavedRecipe(id);
                    });
                });
            }

        } catch (err) {
            libraryContent.innerHTML = `<div class="error">Failed to load library: ${err.message}</div>`;
        }
    }

    // --- LIBRARY SEARCH ---
    let librarySearchTimeout = null;
    librarySearchInput.addEventListener('input', (e) => {
        const q = e.target.value.trim();
        clearTimeout(librarySearchTimeout);
        librarySearchTimeout = setTimeout(() => {
            loadLibrary(q);
        }, 300);
    });

    async function viewSavedRecipe(id) {
        showView(viewScrape); // Show skeleton while loading
        viewScrape.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading recipe...</p></div>';

        try {
            const res = await fetch(`/api/recipes/${id}`);
            const data = await res.json();
            
            if (data.success) {
                // Restore scrape view
                viewScrape.innerHTML = document.querySelector('#view-scrape').innerHTML; 
                // Re-bind (a bit hacky but works for vanilla JS)
                location.reload(); // Safer to reload and redirect, or just populate
                // Let's just populate
            }
        } catch (err) {
             alert('Error: ' + err.message);
        }
        
    }
    
    // Better viewSavedRecipe without reloading
    async function viewSavedRecipe(id) {
        libraryContent.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
        try {
            const res = await fetch(`/api/recipes/${id}`);
            const data = await res.json();
            
            if (data.success) {
                populateRecipeReader(data.recipe);
                currentScrapedRecipe = null;
                currentViewedId = data.recipe.id;
                
                // Hide save button since it's already saved
                actionSave.style.display = 'none';
                actionDelete.classList.remove('hidden');
                showView(viewReader);
            }
        } catch (err) {
             alert('Error loading recipe: ' + err.message);
             loadLibrary();
        }
    }

    
    // --- DELETING ---
    actionDelete.addEventListener('click', async () => {
        if (!currentViewedId) return;
        if (!confirm("Are you sure you want to delete this recipe?")) return;
        
        try {
            const res = await fetch(`/api/recipes/${currentViewedId}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                actionMenu.classList.remove('show');
                loadLibrary();
            } else {
                throw new Error(data.error);
            }
        } catch (err) {
            alert('Error deleting recipe: ' + err.message);
        }
    });

    // --- POPULATE READER ---
    function populateRecipeReader(data) {
        actionSource.href = data.source_url;

        elCategory.value = data.category || "Lunch";
        elTitle.textContent = data.title || "Recipe";
        
        if (data.description) {
            elDesc.textContent = data.description;
            elDesc.classList.remove('hidden');
        } else {
            elDesc.classList.add('hidden');
        }
        
        if (data.image) {
            elImage.src = data.image;
            elSysImageContainer.classList.remove('hidden');
        } else {
            elImage.src = '';
            elSysImageContainer.classList.add('hidden');
        }
        
        setMeta(wrapYields, elYields, data.yields);
        setMeta(wrapPrep, elPrep, data.prep_time);
        setMeta(wrapCook, elCook, data.cook_time);
        setMeta(wrapTotal, elTotal, data.total_time);

        currentOriginalIngredients = data.ingredients || [];
        unitState = 'original';
        btnConvertUnits.textContent = 'Units: Original';
        
        renderIngredientsList(currentOriginalIngredients);

        listInstructions.innerHTML = '';
        if (data.instructions && data.instructions.length > 0) {
            data.instructions.forEach(inst => {
                const li = document.createElement('li');
                li.textContent = inst;
                listInstructions.appendChild(li);
            });
        }
    }
    
    function setMeta(container, el, value) {
        if (value) {
            el.textContent = value;
            container.classList.remove('hidden');
        } else {
            container.classList.add('hidden');
        }
    }

    // --- CATEGORY UPDATES ---
    elCategory.addEventListener('change', async (e) => {
        const newCategory = e.target.value;
        let success = false;
        
        if (currentViewedId) {
            try {
                const res = await fetch(`/api/recipes/${currentViewedId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ category: newCategory })
                });
                const data = await res.json();
                if (data.success) {
                    success = true;
                } else {
                    console.error("Failed to update category", data.error);
                }
            } catch (err) {
                console.error("Failed to update category", err);
            }
        } else if (currentScrapedRecipe) {
            currentScrapedRecipe.category = newCategory;
            success = true; // Memory update success
        }
        
        if (success) {
            elCategorySavedMsg.style.opacity = '1';
            setTimeout(() => {
                elCategorySavedMsg.style.opacity = '0';
            }, 2000);
        }
    });

    // --- UNIT CONVERSION ---
    function renderIngredientsList(ings) {
        listIngredients.innerHTML = '';
        ings.forEach(ing => {
            const li = document.createElement('li');
            li.textContent = ing;
            listIngredients.appendChild(li);
        });
    }

    function parseAndConvertValue(strValue, rate) {
        let parts = strValue.trim().split(' ');
        let decimal = 0;
        if (parts.length === 2 && parts[1].includes('/')) {
            let [num, den] = parts[1].split('/');
            decimal = parseFloat(parts[0]) + (parseFloat(num)/parseFloat(den));
        } else if (parts.length === 1 && parts[0].includes('/')) {
            let [num, den] = parts[0].split('/');
            decimal = parseFloat(num)/parseFloat(den);
        } else {
            decimal = parseFloat(strValue);
        }
        if (isNaN(decimal)) return strValue;
        
        let converted = decimal * rate;
        // Keep to at most 2 decimal places to avoid noisy fractions, strip trailing zero decimals 
        return (Math.round(converted * 100) / 100).toString();
    }

    function convertIngredientsText(ingredients, targetSystem) {
        const metricToImperial = [
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(g|gram|grams)\b/gi, rate: 1/28.35, unit: 'oz' },
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(kg|kilo|kilogram|kilograms)\b/gi, rate: 2.205, unit: 'lb' },
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(ml|milliliter|milliliters)\b/gi, rate: 1/29.57, unit: 'fl oz' },
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(l|liter|liters)\b/gi, rate: 1.057, unit: 'qt' },
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(c(elsius)?)\b/gi, rate: 'C2F', unit: 'F' }
        ];
        
        const imperialToMetric = [
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(oz|ounce|ounces)\b/gi, rate: 28.35, unit: 'g' },
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(lb|lbs|pound|pounds)\b/gi, rate: 0.4535, unit: 'kg' },
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(fl oz|fluid ounce|fluid ounces)\b/gi, rate: 29.57, unit: 'ml' },
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(cup|cups)\b/gi, rate: 240, unit: 'ml' },
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(tbsp|tablespoon|tablespoons)\b/gi, rate: 15, unit: 'ml' },
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(tsp|teaspoon|teaspoons)\b/gi, rate: 5, unit: 'ml' },
            { regex: /(?<!\d\s)([\d\s\.\/]+)\s*(f(ahrenheit)?)\b/gi, rate: 'F2C', unit: 'C' }
        ];

        const rules = targetSystem === 'metric' ? imperialToMetric : metricToImperial;

        return ingredients.map(ing => {
            let newIng = ing;
            for (let rule of rules) {
                newIng = newIng.replace(rule.regex, (match, valStr, unitStr) => {
                    let converted;
                    if (rule.rate === 'F2C') {
                        let c = (parseFloat(valStr) - 32) * 5/9;
                        converted = Math.round(c);
                    } else if (rule.rate === 'C2F') {
                        let f = (parseFloat(valStr) * 9/5) + 32;
                        converted = Math.round(f);
                    } else {
                        converted = parseAndConvertValue(valStr, rule.rate);
                    }
                    if (converted === valStr) return match;
                    return `${converted} ${rule.unit}`;
                });
            }
            return newIng;
        });
    }

    btnConvertUnits.addEventListener('click', () => {
        if (!currentOriginalIngredients || currentOriginalIngredients.length === 0) return;
        
        if (unitState === 'original') {
            unitState = 'metric';
            btnConvertUnits.textContent = 'Units: Metric';
            renderIngredientsList(convertIngredientsText(currentOriginalIngredients, 'metric'));
        } else if (unitState === 'metric') {
            unitState = 'imperial';
            btnConvertUnits.textContent = 'Units: Imperial';
            renderIngredientsList(convertIngredientsText(currentOriginalIngredients, 'imperial'));
        } else {
            unitState = 'original';
            btnConvertUnits.textContent = 'Units: Original';
            renderIngredientsList(currentOriginalIngredients);
        }
    });

});
