import { useEffect, useState } from 'react';
import { Eye, Search } from 'lucide-react';
import { getDatabaseRows, getDatabaseTables } from '../../services/api';

const PAGE_SIZE = 25;

function tableSchema(table) {
  return table?.schema || table?.schema_name;
}

function cellText(value) {
  if (value == null) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export default function DatabaseBrowser() {
  const [tables, setTables] = useState([]);
  const [selected, setSelected] = useState(null);
  const [rowsPayload, setRowsPayload] = useState(null);
  const [viewing, setViewing] = useState(null);
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadTables = async () => {
    const { data } = await getDatabaseTables();
    setTables(data || []);
  };

  const loadRows = async (table, nextOffset = 0, nextSearch = search) => {
    const { data } = await getDatabaseRows(tableSchema(table), table.name, {
      limit: PAGE_SIZE,
      offset: nextOffset,
      search: nextSearch,
    });
    setRowsPayload(data);
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    loadTables()
      .catch((err) => setError(err.response?.data?.detail || 'Could not load tables.'))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const openTable = async (table) => {
    setError(null);
    setSelected(table);
    setViewing(null);
    setSearch('');
    setOffset(0);
    try {
      await loadRows(table, 0, '');
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load rows.');
    }
  };

  const applySearch = async (event) => {
    event.preventDefault();
    if (!selected) return;
    setOffset(0);
    try {
      await loadRows(selected, 0, search);
    } catch (err) {
      setError(err.response?.data?.detail || 'Search failed.');
    }
  };

  const changePage = async (nextOffset) => {
    if (!selected) return;
    setOffset(nextOffset);
    try {
      await loadRows(selected, nextOffset, search);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load page.');
    }
  };

  if (loading) {
    return <p className="text-sm text-muted">Loading allowlisted tables…</p>;
  }

  const total = rowsPayload?.total || 0;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="grid lg:grid-cols-4 gap-4">
      <div className="card p-4 max-h-[70vh] overflow-y-auto">
        <p className="text-xs uppercase tracking-wider text-muted font-semibold mb-2">Allowlisted tables</p>
        <div className="space-y-1">
          {tables.map((table) => (
            <button
              key={`${tableSchema(table)}.${table.name}`}
              type="button"
              onClick={() => openTable(table)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
                tableSchema(selected) === tableSchema(table) && selected?.name === table.name
                  ? 'nav-active'
                  : 'text-col hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              <span className="font-medium">{table.label || table.name}</span>
              <span className="text-xs text-muted ml-2">{table.rows}</span>
              <span className="block text-[10px] uppercase tracking-wide text-amber-700 dark:text-amber-400 mt-0.5">
                Read only
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="lg:col-span-3 space-y-4">
        {error && (
          <div className="card bg-red-50 dark:bg-red-900/20 border border-red-200 text-red-700 text-sm px-4 py-3">
            {error}
          </div>
        )}

        {!selected && (
          <div className="card p-6 text-sm text-muted space-y-2">
            <p>Select a table to inspect records. This console is read-only.</p>
            <p>
              Business edits belong in <span className="font-medium text-col">Data Management</span>.
              Credentials, sessions, migrations, and checkpoint tables are blocked on the server.
            </p>
          </div>
        )}

        {selected && rowsPayload && (
          <>
            <div className="card p-4 flex flex-wrap items-center gap-3">
              <div>
                <p className="font-semibold text-col">{rowsPayload.label || selected.name}</p>
                <p className="text-xs text-muted">{tableSchema(selected)}.{selected.name}</p>
              </div>
              <span className="text-[11px] font-semibold uppercase tracking-wider px-2 py-1 rounded-full bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
                Read only
              </span>
              {rowsPayload.notes && <p className="text-xs text-muted w-full">{rowsPayload.notes}</p>}
              <form onSubmit={applySearch} className="flex gap-2 ml-auto">
                <input
                  className="input-field w-56"
                  placeholder="Search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <button type="submit" className="btn-secondary inline-flex items-center gap-1">
                  <Search size={14} /> Search
                </button>
              </form>
            </div>

            <div className="card p-0 overflow-auto max-h-[46vh]">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 dark:bg-slate-800/50 text-muted sticky top-0">
                  <tr>
                    {(rowsPayload.columns || []).map((column) => (
                      <th key={column.name} className="text-left px-3 py-2 font-semibold whitespace-nowrap">
                        {column.name}
                      </th>
                    ))}
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-col">
                  {(rowsPayload.rows || []).map((row, index) => (
                    <tr key={row.id || index} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      {(rowsPayload.columns || []).map((column) => (
                        <td key={column.name} className="px-3 py-2 font-mono text-col max-w-[220px] truncate">
                          {cellText(row.data?.[column.name])}
                        </td>
                      ))}
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <button type="button" className="text-blue-600 font-medium inline-flex items-center gap-1" onClick={() => setViewing(row)}>
                          <Eye size={12} /> View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!rowsPayload.rows?.length && (
                <p className="px-4 py-6 text-sm text-muted">No rows match this view.</p>
              )}
            </div>

            <div className="flex items-center justify-between text-xs text-muted">
              <span>{total ? `${offset + 1}–${pageEnd} of ${total}` : '0 records'}</span>
              <div className="flex gap-2">
                <button type="button" className="btn-secondary" disabled={offset === 0} onClick={() => changePage(Math.max(0, offset - PAGE_SIZE))}>
                  Previous
                </button>
                <button type="button" className="btn-secondary" disabled={pageEnd >= total} onClick={() => changePage(offset + PAGE_SIZE)}>
                  Next
                </button>
              </div>
            </div>
          </>
        )}

        {viewing && (
          <div className="card p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-col">Record {viewing.id || ''}</h3>
              <button type="button" className="btn-secondary" onClick={() => setViewing(null)}>Close</button>
            </div>
            <dl className="grid sm:grid-cols-2 gap-3 text-sm">
              {Object.entries(viewing.data || {}).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-xs uppercase tracking-wider text-muted">{key}</dt>
                  <dd className="font-mono text-col break-all">{cellText(value)}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </div>
    </div>
  );
}
