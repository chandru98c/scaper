function loadHistory() {
    fetch('/api/files')
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('historyList');
            if (!container) return;

            container.innerHTML = '';

            if (data.files.length === 0) {
                container.innerHTML = `
                    <div class="p-8 text-center text-ios-subtext opacity-60">
                        <p class="text-sm">No files scraped yet.</p>
                    </div>`;
                return;
            }

            data.files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'flex items-center justify-between p-4 border-b border-ios-border last:border-0 hover:bg-ios-bg transition-colors duration-200';

                item.innerHTML = `
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-lg bg-ios-green bg-opacity-10 text-ios-green flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" opacity="0.8" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                            </svg>
                        </div>
                        <div>
                            <div class="text-[13px] font-semibold text-ios-text truncate max-w-[200px] md:max-w-md" title="${file.name}">${file.name}</div>
                            <div class="text-[11px] text-ios-subtext font-medium">${file.date} • ${file.size}</div>
                        </div>
                    </div>
                    <div class="flex gap-2">
                         <button onclick="fetch('/api/open/${file.name}')" class="text-xs font-bold text-ios-text bg-ios-input border border-ios-border px-3 py-1.5 rounded-lg hover:bg-opacity-80 transition">
                            Open
                        </button>
                        <a href="/download/${file.name}" class="text-xs font-bold text-ios-blue bg-ios-blue bg-opacity-10 px-3 py-1.5 rounded-lg hover:bg-opacity-20 transition">
                            Download
                        </a>
                    </div>
                `;
                container.appendChild(item);
            });
        })
        .catch(err => console.error("Failed to load history:", err));
}

// Auto load on start and refresh every 10s
document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    setInterval(loadHistory, 10000); // Polling for updates
});
