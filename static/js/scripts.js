const operators = [
    {value: "=", label: "equals"},
    {value: "!=", label: "not equals"},
    {value: ">", label: "greater than"},
    {value: "<", label: "less than"},
    {value: ">=", label: "greater than or equal"},
    {value: "<=", label: "less than or equal"},
    {value: "IN", label: "in list (comma-sep)"},
    {value: "NOT IN", label: "not in list (comma-sep)"},
    {value: "LIKE", label: "contains (case-sensitive)"}
];

let queryResults = null; 
let parquetFiles = null; 
const API_BASE_URL = 'http://127.0.0.1:5001'; 

function createOperatorSelect() {
    const select = document.createElement('select');
    select.className = 'form-select operator-select';
    select.innerHTML = '<option value="">Select Operator</option>' +
        operators.map(op =>
            `<option value="${op.value}">${op.label}</option>`
        ).join('');
    return select;
}

function createColumnInput() {
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'form-control column-input';
    input.placeholder = 'Column Name';
    return input;
}

function addFilter() {
    const filterContainer = document.createElement('div');
    filterContainer.className = 'filter-row d-flex align-items-center gap-2'; 

    const colInput = createColumnInput();

    const opSelect = createOperatorSelect();

    const valueInput = document.createElement('input');
    valueInput.type = 'text';
    valueInput.className = 'form-control value-input flex-grow-1'; 
    valueInput.placeholder = 'Value (use comma for IN/NOT IN lists)';

    const removeBtn = document.createElement('button');
    removeBtn.textContent = 'Remove';
    removeBtn.className = 'btn btn-outline-danger btn-sm';
    removeBtn.onclick = () => filterContainer.remove();

    filterContainer.appendChild(colInput);
    filterContainer.appendChild(opSelect);
    filterContainer.appendChild(valueInput);
    filterContainer.appendChild(removeBtn);

    document.getElementById('filters').appendChild(filterContainer);
}

function getFilters() {
    const filters = [];
    document.querySelectorAll('.filter-row').forEach(row => {
        const columnInput = row.querySelector('.column-input');
        const operatorSelect = row.querySelector('.operator-select');
        const valueInput = row.querySelector('.value-input');

        const column = columnInput.value.trim();
        const operator = operatorSelect.value;
        let value = valueInput.value.trim();

        if (column && operator && value) {
            if (operator === 'IN' || operator === 'NOT IN') {
                value = value.split(',').map(s => s.trim()).filter(s => s !== '');
                if (value.length === 0) return; 
            }

            filters.push({ column, operator, value });
        }
    });
    return filters;
}

async function findFiles() {
    clearResults();
    const filters = getFilters();
    console.log("Finding files with filters:", filters);

    try {
        const response = await fetch(`${API_BASE_URL}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filters })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP error ${response.status}`);
        }

        parquetFiles = data.parquet_files || [];
        displayParquetFiles(parquetFiles);
        document.getElementById('resultActionButtons').style.display = 'none'; 

    } catch (error) {
        console.error('Error finding files:', error);
        displayError(`Error finding files: ${error.message}`);
        parquetFiles = null;
    }
}

async function executeCustomSql() {
    clearResults();
    const sql = document.getElementById('sqlQueryInput').value.trim();
    if (!sql) {
        alert('Please enter a SQL query.');
        return;
    }
    console.log("Executing SQL:", sql);

    try {
        const response = await fetch(`${API_BASE_URL}/execute_sql`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sql })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP error ${response.status}`);
        }

        queryResults = data.results || [];
        displayResultsTable(queryResults);
        document.getElementById('resultActionButtons').style.display = 'flex';

    } catch (error) {
        console.error('Error executing SQL:', error);
        displayError(`Error executing SQL: ${error.message}`);
        queryResults = null;
    }
}

function displayResultsTable(results) {
    const resultsContent = document.getElementById('resultsContent');
    const resultsSection = document.getElementById('resultsSection');
    const resultsTitle = document.getElementById('resultsTitle');

    resultsSection.style.display = 'block';
    resultsTitle.textContent = 'SQL Query Results';

    if (!Array.isArray(results) || results.length === 0) {
        resultsContent.innerHTML = '<div class="alert alert-info">The query returned no results.</div>';
        return;
    }

    const columns = Object.keys(results[0]);
    const tableContainer = document.createElement('div');
    tableContainer.className = 'table-container';

    const table = document.createElement('table');
    table.className = 'table table-striped table-bordered table-hover';

    // Create header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    // Create body
    const tbody = document.createElement('tbody');
    results.forEach(row => {
        const tr = document.createElement('tr');
        columns.forEach(col => {
            const td = document.createElement('td');
            td.textContent = row[col] !== null ? row[col] : 'NULL';
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);
    tableContainer.appendChild(table);
    resultsContent.innerHTML = '';
    resultsContent.appendChild(tableContainer);
}

function displayParquetFiles(files) {
    const resultsContent = document.getElementById('resultsContent');
    const resultsSection = document.getElementById('resultsSection');
    const resultsTitle = document.getElementById('resultsTitle');

    resultsSection.style.display = 'block';
    resultsTitle.textContent = 'Available Parquet Files';

    if (!Array.isArray(files) || files.length === 0) {
        resultsContent.innerHTML = '<div class="alert alert-warning">No matching parquet files found.</div>';
        return;
    }

    const fileList = document.createElement('ul');
    fileList.className = 'list-group';

    files.forEach(file => {
        const item = document.createElement('li');
        item.className = 'list-group-item d-flex justify-content-between align-items-center';
        item.innerHTML = `
            <span>${file}</span>
            <button class="btn btn-sm btn-primary" onclick="executeCustomSql('SELECT * FROM \\'${file}\\' LIMIT 10')">View Sample</button>
        `;
        fileList.appendChild(item);
    });

    resultsContent.innerHTML = '';
    resultsContent.appendChild(fileList);
}

function displayMessage(message) {
    const resultsContent = document.getElementById('resultsContent');
    const resultsSection = document.getElementById('resultsSection');
    
    resultsSection.style.display = 'block';
    resultsContent.innerHTML = `<div class="alert alert-info">${message}</div>`;
}

function displayError(errorMessage) {
    const resultsContent = document.getElementById('resultsContent');
    const resultsSection = document.getElementById('resultsSection');
    
    resultsSection.style.display = 'block';
    resultsContent.innerHTML = `<div class="alert alert-danger">${errorMessage}</div>`;
}

function exportToCsv() {
    if (!queryResults || queryResults.length === 0) {
        alert('No results to export!');
        return;
    }

    const columns = Object.keys(queryResults[0]);
    const header = columns.join(',');
    
    const rows = queryResults.map(row => 
        columns.map(col => {
            // Handle values that need escaping (commas, quotes, etc.)
            const val = row[col] !== null ? row[col] : '';
            const escapedVal = typeof val === 'string' ? 
                `"${val.replace(/"/g, '""')}"` : 
                val;
            return escapedVal;
        }).join(',')
    );

    const csvContent = [header, ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'sql_results.csv');
    link.style.display = 'none';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function clearResults() {
    const resultsSection = document.getElementById('resultsSection');
    const resultsContent = document.getElementById('resultsContent');
    
    resultsSection.style.display = 'none';
    resultsContent.innerHTML = '';
}

function clearAll() {
    clearResults();
    document.getElementById('filters').innerHTML = '';
    document.getElementById('sqlQueryInput').value = '';
    document.getElementById('resultActionButtons').style.display = 'none';
    addFilter();
}

// Initialize with one filter row
document.addEventListener('DOMContentLoaded', function() {
    addFilter();
});
