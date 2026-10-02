// ── Utility: map status enum to CSS class ──
function statusClass(status) {
  switch (status) {
    case 'COMPLETED': return 'completed';
    case 'IN_PROGRESS': return 'in-progress';
    case 'REQUIRE_HUMAN_REVIEW': return 'human-review';
    default: return 'not-started';
  }
}

function statusLabel(status) {
  switch (status) {
    case 'COMPLETED': return 'Completed';
    case 'IN_PROGRESS': return 'In Progress';
    case 'REQUIRE_HUMAN_REVIEW': return 'Needs Review';
    default: return 'Not Started';
  }
}

function taskStatusLabel(status) {
  switch (status) {
    case 'COMPLETED': return 'Done';
    case 'IN_PROGRESS': return 'In Progress';
    case 'REQUIRE_HUMAN_REVIEW': return 'Needs Review';
    default: return 'Not Started';
  }
}

function statusIcon(status) {
  switch (status) {
    case 'COMPLETED': return '✓';
    case 'IN_PROGRESS': return '↻';
    case 'REQUIRE_HUMAN_REVIEW': return '!';
    default: return '';
  }
}

// ── Escape text for safe attribute use ──
function escapeAttr(str) {
  return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

// ── Compute completed / total from tasks ──
function taskProgress(epic) {
  var done = 0;
  epic.tasks.forEach(function (t) { if (t.status === 'COMPLETED') done++; });
  return { done: done, total: epic.tasks.length };
}

// ── Build a lookup index: epicId + taskIndex -> task object ──
var _taskIndex = {};
function buildTaskIndex(data) {
  data.epics.forEach(function (epic) {
    epic.tasks.forEach(function (task, idx) {
      _taskIndex[epic.id + ':' + idx] = {
        task: task,
        epic: epic
      };
    });
  });
}

// ── Data access (loaded via <script src="data.js">) ──
function loadData() {
  return window.PROJECT_DATA;
}

// ══════════════════════════════════════════
//  MODAL
// ══════════════════════════════════════════

function openTaskModal(epicId, taskIndex) {
  var entry = _taskIndex[epicId + ':' + taskIndex];
  if (!entry) return;

  var task = entry.task;
  var epic = entry.epic;
  var tsc = statusClass(task.status);

  // Header
  var headerEl = document.getElementById('modalHeader');
  headerEl.innerHTML =
    '<h2>' + (task.id ? '<span class="modal-task-id">' + task.id + '</span>' : '') + task.name + '</h2>' +
    '<div style="display:flex;align-items:center;gap:0.75rem;">' +
    '  <span class="badge ' + tsc + '">' + taskStatusLabel(task.status) + '</span>' +
    '  <button class="modal-close" id="modalClose">&times;</button>' +
    '</div>';

  // Meta
  var metaEl = document.getElementById('modalMeta');
  var metaHtml = '<span class="modal-meta-item"><strong>Epic:</strong> ' + epic.number + ' — ' + epic.name + '</span>';
  if (task.dependencies.length > 0) {
    metaHtml += '<span class="modal-meta-item"><strong>Dependencies:</strong> ' +
      task.dependencies.map(function (d) { return '<span class="dep-tag">' + escapeAttr(d) + '</span>'; }).join(' ') +
      '</span>';
  }
  if (task.prLinks && task.prLinks.length > 0) {
    metaHtml += '<span class="modal-meta-item"><strong>PRs / commits:</strong> ' +
      task.prLinks.map(function (url) {
        var num = url.match(/\/pull\/(\d+)/);
        var sha = url.match(/\/commit\/([0-9a-f]{7})/);
        var label = num ? '#' + num[1] : (sha ? sha[1] : url);
        return '<a href="' + escapeAttr(url) + '" target="_blank" rel="noopener">' + label + '</a>';
      }).join(', ') +
      '</span>';
  }
  if (task.links && task.links.length > 0) {
    metaHtml += '<span class="modal-meta-item"><strong>Links:</strong> ' +
      task.links.map(function (l) {
        return '<a href="' + escapeAttr(l.url) + '" target="_blank" rel="noopener">' + escapeAttr(l.label) + '</a>';
      }).join(', ') +
      '</span>';
  }
  metaEl.innerHTML = metaHtml;

  // Body
  var bodyEl = document.getElementById('modalBody');
  if (task.fullDetails) {
    bodyEl.innerHTML = task.fullDetails;
  } else {
    bodyEl.innerHTML = '<p>' + task.details + '</p>';
  }

  // Show
  document.getElementById('modalOverlay').classList.add('open');
  document.body.style.overflow = 'hidden';

  // Close handlers
  document.getElementById('modalClose').addEventListener('click', closeModal);
}

function closeModal() {
  document.getElementById('modalOverlay').classList.remove('open');
  document.body.style.overflow = '';
}

function initModal() {
  var overlay = document.getElementById('modalOverlay');
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) closeModal();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeModal();
  });
}

// ══════════════════════════════════════════
//  SIDEBAR
// ══════════════════════════════════════════

function renderSidebar(data) {
  var nav = document.getElementById('sidebarNav');
  var html = '';

  // Overview link
  html += '<div class="nav-section">';
  html += '  <a href="#overview" class="nav-misc-link">Overview</a>';
  html += '</div>';
  html += '<div class="nav-divider"></div>';

  // Epics
  data.epics.forEach(function (epic) {
    var sc = statusClass(epic.status);
    html += '<div class="nav-section" data-epic="' + epic.id + '">';

    // Epic toggle row
    html += '  <div class="nav-epic-toggle" data-target="' + epic.id + '">';
    html += '    <span class="nav-dot ' + sc + '">' + statusIcon(epic.status) + '</span>';
    html += '    <span class="nav-epic-label">Epic ' + epic.number + ' — ' + escapeAttr(epic.shortName) + '</span>';
    html += '    <span class="nav-epic-chevron">&#9662;</span>';
    html += '  </div>';

    // Task sub-list
    html += '  <ul class="nav-task-list">';
    epic.tasks.forEach(function (task, idx) {
      var tc = statusClass(task.status);
      var hasDetails = !!task.fullDetails;
      html += '    <li class="nav-task-item' + (hasDetails ? ' clickable' : '') + '"' +
        ' data-task-status="' + task.status + '"' +
        ' data-task-search="' + escapeAttr((task.name + ' ' + task.details).toLowerCase()) + '"' +
        (hasDetails ? ' data-epic="' + epic.id + '" data-task="' + idx + '"' : '') + '>';
      html += '      <span class="nav-task-dot ' + tc + '">' + statusIcon(task.status) + '</span>';
      html += '      <span class="nav-task-id">' + (task.id || '') + '</span>';
      html += '      <span class="nav-task-name">' + escapeAttr(task.name) + '</span>';
      html += '    </li>';
    });
    html += '  </ul>';

    html += '</div>';
  });

  // Key decisions link
  html += '<div class="nav-divider"></div>';
  html += '<div class="nav-section">';
  html += '  <a href="#key-decisions" class="nav-misc-link">Key Decisions</a>';
  html += '</div>';

  nav.innerHTML = html;

  // Attach epic toggle behaviour
  nav.querySelectorAll('.nav-epic-toggle').forEach(function (toggle) {
    toggle.addEventListener('click', function () {
      var section = toggle.closest('.nav-section');
      var wasExpanded = section.classList.contains('expanded');

      // Collapse all
      nav.querySelectorAll('.nav-section.expanded').forEach(function (s) {
        s.classList.remove('expanded');
      });

      // Toggle clicked (accordion)
      if (!wasExpanded) {
        section.classList.add('expanded');
      }

      // Scroll main content to this epic and open it
      var targetId = toggle.getAttribute('data-target');
      var targetEl = document.getElementById(targetId);
      if (targetEl) {
        targetEl.classList.add('open');
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // Attach sidebar task click → open modal
  nav.querySelectorAll('.nav-task-item.clickable').forEach(function (item) {
    item.addEventListener('click', function (e) {
      e.stopPropagation();
      var epicId = item.getAttribute('data-epic');
      var taskIdx = parseInt(item.getAttribute('data-task'), 10);
      openTaskModal(epicId, taskIdx);
    });
  });
}

// ══════════════════════════════════════════
//  MAIN CONTENT
// ══════════════════════════════════════════

function renderContent(data) {
  var el = document.getElementById('pageContent');
  var html = '';

  // Title
  html += '<h1>' + data.meta.title + '</h1>';
  html += '<p class="subtitle">Last updated: ' + data.meta.lastUpdated + ' &nbsp;|&nbsp; Track overall progress across all development epics</p>';

  // Overview stats
  html += renderOverview(data);

  // Filter bar
  html += renderFilterBar(data);

  // Epics
  data.epics.forEach(function (epic) {
    html += renderEpic(epic);
  });

  // Key decisions
  html += renderKeyDecisions(data.keyDecisions);

  el.innerHTML = html;
}

// ── Overview stats cards ──
function renderOverview(data) {
  var c = countTasksByStatus(data);
  var html = '<div id="overview" class="overview">';
  html += statCard('total', c._total, 'Total Tasks');
  html += statCard('completed', c.COMPLETED, 'Completed');
  html += statCard('in-progress', c.IN_PROGRESS, 'In Progress');
  if (c.REQUIRE_HUMAN_REVIEW > 0) {
    html += statCard('in-progress', c.REQUIRE_HUMAN_REVIEW, 'Needs Review');
  }
  html += statCard('not-started', c.NOT_STARTED, 'Not Started');
  html += '</div>';
  return html;
}

function statCard(cls, num, label) {
  return '<div class="stat-card ' + cls + '">' +
    '<span class="number">' + num + '</span>' +
    '<span class="label">' + label + '</span>' +
    '</div>';
}

// ── Single epic section ──
function renderEpic(epic) {
  var sc = statusClass(epic.status);
  var prog = taskProgress(epic);

  var html = '<div id="' + epic.id + '" class="epic" data-epic-status="' + epic.status + '">';

  // Header
  html += '<div class="epic-header">';
  html += '  <div class="epic-title">';
  html += '    <span class="epic-number ' + sc + '">Epic ' + epic.number + '</span>';
  html += '    <span class="badge ' + sc + '">' + statusLabel(epic.status) + '</span>';
  html += '    <span class="epic-name">' + epic.name + '</span>';
  html += '  </div>';
  html += '  <div class="epic-meta">';
  html += '    <span class="epic-progress">' + prog.done + ' / ' + prog.total + ' tasks</span>';
  html += '    <span class="chevron">&#9662;</span>';
  html += '  </div>';
  html += '</div>';

  // Body
  html += '<div class="epic-body">';
  html += '  <p class="epic-description">' + epic.description + '</p>';

  // Deployment grid (Epic 8)
  if (epic.deploymentCards && epic.deploymentCards.length > 0) {
    html += '<div class="deployment-grid">';
    epic.deploymentCards.forEach(function (card) {
      html += '<div class="deploy-card">';
      html += '  <h4>' + card.title + '</h4>';
      html += '  <ul>';
      card.items.forEach(function (item) {
        html += '    <li>' + item + '</li>';
      });
      html += '  </ul>';
      html += '</div>';
    });
    html += '</div>';
  }

  // Task table
  if (epic.tasks.length > 0) {
    var hasDeps = epic.tasks.some(function (t) { return t.dependencies.length > 0; });

    html += '<table>';
    html += '<thead><tr>';
    html += '<th>Task</th><th>Status</th><th>Details</th>';
    if (hasDeps) html += '<th>Dependencies</th>';
    html += '</tr></thead>';
    html += '<tbody>';

    epic.tasks.forEach(function (task, idx) {
      var tsc = statusClass(task.status);
      var hasDetails = !!task.fullDetails;
      html += '<tr data-task-status="' + task.status + '" data-task-search="' + escapeAttr((task.name + ' ' + task.details).toLowerCase()) + '"' + (hasDetails ? ' class="clickable-task" data-epic="' + epic.id + '" data-task="' + idx + '"' : '') + '>';
      html += '<td class="task-name"><span class="task-id">' + (task.id || '') + '</span>' + task.name + '</td>';
      html += '<td class="status-cell"><span class="badge ' + tsc + '">' + taskStatusLabel(task.status) + '</span></td>';
      html += '<td>' + task.details + '</td>';
      if (hasDeps) {
        html += '<td class="deps">';
        if (task.dependencies.length === 0) {
          html += '—';
        } else {
          task.dependencies.forEach(function (dep) {
            html += '<span class="dep-tag">' + escapeAttr(dep) + '</span>';
          });
        }
        html += '</td>';
      }
      html += '</tr>';
    });

    html += '</tbody></table>';
  }

  html += '</div>'; // epic-body
  html += '</div>'; // epic
  return html;
}

// ── Key decisions ──
function renderKeyDecisions(decisions) {
  var html = '<div id="key-decisions" class="notes">';
  html += '<h3>Key Decisions &amp; Constraints</h3>';
  html += '<ul>';
  decisions.forEach(function (d) {
    html += '<li><strong>' + d.label + ':</strong> ' + d.text + '</li>';
  });
  html += '</ul>';
  html += '</div>';
  return html;
}

// ══════════════════════════════════════════
//  INTERACTIVITY
// ══════════════════════════════════════════

function initEpicToggles() {
  document.querySelectorAll('.epic-header').forEach(function (header) {
    header.addEventListener('click', function () {
      header.parentElement.classList.toggle('open');
    });
  });
}

function initTaskClicks() {
  document.querySelectorAll('.clickable-task').forEach(function (row) {
    row.addEventListener('click', function () {
      var epicId = row.getAttribute('data-epic');
      var taskIdx = parseInt(row.getAttribute('data-task'), 10);
      openTaskModal(epicId, taskIdx);
    });
  });
}

function collapseCompletedEpics() {
  // Collapse all epics
  document.querySelectorAll('.epic').forEach(function (epic) {
    epic.classList.remove('open');
  });
  // Apply filters (hides completed epics since toggle is off by default)
  applyFilters();
  // Open the first in-progress epic if any
  var ip = document.querySelector('.epic-number.in-progress');
  if (ip) {
    ip.closest('.epic').classList.add('open');
  }
}

function initMobileSidebar() {
  var toggle = document.getElementById('sidebarToggle');
  var sidebar = document.getElementById('sidebar');
  var overlay = document.getElementById('sidebarOverlay');

  toggle.addEventListener('click', function () {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
  });

  overlay.addEventListener('click', function () {
    sidebar.classList.remove('open');
    overlay.classList.remove('open');
  });

  // Close sidebar on nav click (mobile)
  sidebar.querySelectorAll('a, .nav-epic-toggle').forEach(function (link) {
    link.addEventListener('click', function () {
      if (window.innerWidth <= 900) {
        sidebar.classList.remove('open');
        overlay.classList.remove('open');
      }
    });
  });
}

function initScrollSpy() {
  var nav = document.getElementById('sidebarNav');
  var allToggles = nav.querySelectorAll('.nav-epic-toggle');
  var allMiscLinks = nav.querySelectorAll('.nav-misc-link');

  // Build target map: id -> { element, type }
  var linkMap = {};

  allMiscLinks.forEach(function (link) {
    var hash = link.getAttribute('href');
    if (hash && hash.startsWith('#')) {
      linkMap[hash.substring(1)] = { el: link, type: 'misc' };
    }
  });

  allToggles.forEach(function (toggle) {
    var targetId = toggle.getAttribute('data-target');
    if (targetId) {
      linkMap[targetId] = { el: toggle, type: 'epic' };
    }
  });

  var targetIds = Object.keys(linkMap);
  var targets = targetIds.map(function (id) { return document.getElementById(id); }).filter(Boolean);
  var visibleSet = new Set();

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        visibleSet.add(entry.target.id);
      } else {
        visibleSet.delete(entry.target.id);
      }
    });

    // Find topmost visible target
    var activeId = null;
    for (var i = 0; i < targets.length; i++) {
      if (visibleSet.has(targets[i].id)) {
        activeId = targets[i].id;
        break;
      }
    }

    if (activeId) {
      // Remove all active states
      allToggles.forEach(function (t) { t.classList.remove('active'); });
      allMiscLinks.forEach(function (l) { l.classList.remove('active'); });

      var entry = linkMap[activeId];
      if (entry) {
        entry.el.classList.add('active');

        // Auto-expand the active epic in sidebar
        if (entry.type === 'epic') {
          var section = entry.el.closest('.nav-section');
          if (section && !section.classList.contains('expanded')) {
            nav.querySelectorAll('.nav-section.expanded').forEach(function (s) {
              s.classList.remove('expanded');
            });
            section.classList.add('expanded');
          }
        }
      }
    }
  }, {
    rootMargin: '-5% 0px -70% 0px',
    threshold: 0
  });

  targets.forEach(function (el) { observer.observe(el); });
}

// ══════════════════════════════════════════
//  FILTER BAR
// ══════════════════════════════════════════

function countTasksByStatus(data) {
  var counts = { COMPLETED: 0, IN_PROGRESS: 0, REQUIRE_HUMAN_REVIEW: 0, NOT_STARTED: 0 };
  data.epics.forEach(function (epic) {
    epic.tasks.forEach(function (task) {
      counts[task.status] = (counts[task.status] || 0) + 1;
    });
  });
  counts._total = counts.COMPLETED + counts.IN_PROGRESS + counts.REQUIRE_HUMAN_REVIEW + counts.NOT_STARTED;
  return counts;
}

function renderFilterBar(data) {
  var c = countTasksByStatus(data);

  var html = '<div class="filter-bar" id="filterBar">';

  // Search
  html += '<div class="filter-search">';
  html += '  <input type="text" id="filterSearch" placeholder="Search tasks..." />';
  html += '</div>';

  // Status chips
  html += '<div class="filter-chips">';
  html += '  <button class="filter-chip active" data-filter="all">All <span class="chip-count">' + c._total + '</span></button>';
  html += '  <button class="filter-chip" data-filter="COMPLETED"><span class="chip-icon completed">✓</span> Done <span class="chip-count">' + c.COMPLETED + '</span></button>';
  html += '  <button class="filter-chip" data-filter="IN_PROGRESS"><span class="chip-icon in-progress">↻</span> In Progress <span class="chip-count">' + c.IN_PROGRESS + '</span></button>';
  if (c.REQUIRE_HUMAN_REVIEW > 0) {
    html += '  <button class="filter-chip" data-filter="REQUIRE_HUMAN_REVIEW"><span class="chip-icon human-review">!</span> Review <span class="chip-count">' + c.REQUIRE_HUMAN_REVIEW + '</span></button>';
  }
  html += '  <button class="filter-chip" data-filter="NOT_STARTED"><span class="chip-icon not-started"></span> Not Started <span class="chip-count">' + c.NOT_STARTED + '</span></button>';
  html += '</div>';

  // Show completed epics toggle (off by default — completed epics are hidden initially)
  html += '<label class="filter-toggle">';
  html += '  <input type="checkbox" id="filterShowCompleted" />';
  html += '  <span>Show completed epics</span>';
  html += '</label>';

  html += '</div>';
  return html;
}

var _activeFilter = 'all';

function applyFilters() {
  var searchEl = document.getElementById('filterSearch');
  var showCompletedEl = document.getElementById('filterShowCompleted');
  if (!searchEl) return;

  var search = searchEl.value.toLowerCase().trim();
  var hideCompletedEpics = showCompletedEl && !showCompletedEl.checked;
  var statusFilter = _activeFilter;

  // Filter task rows in tables
  document.querySelectorAll('tr[data-task-status]').forEach(function (row) {
    var status = row.getAttribute('data-task-status');
    var searchText = row.getAttribute('data-task-search') || '';

    var statusMatch = statusFilter === 'all' || status === statusFilter;
    var searchMatch = !search || searchText.indexOf(search) !== -1;

    if (statusMatch && searchMatch) {
      row.classList.remove('filter-hidden');
    } else {
      row.classList.add('filter-hidden');
    }
  });

  // Hide epics where all tasks are hidden, or epic is completed and toggle is off
  document.querySelectorAll('.epic[data-epic-status]').forEach(function (epic) {
    var epicStatus = epic.getAttribute('data-epic-status');
    var allRows = epic.querySelectorAll('tr[data-task-status]');
    var visibleRows = epic.querySelectorAll('tr[data-task-status]:not(.filter-hidden)');
    if (hideCompletedEpics && epicStatus === 'COMPLETED') {
      epic.classList.add('filter-hidden');
    } else if (allRows.length > 0 && visibleRows.length === 0) {
      epic.classList.add('filter-hidden');
    } else {
      epic.classList.remove('filter-hidden');
      // Auto-open epics that have visible results when actively filtering
      if ((search || statusFilter !== 'all') && visibleRows.length > 0) {
        epic.classList.add('open');
      }
    }
  });

  // Filter sidebar task items
  document.querySelectorAll('.nav-task-item[data-task-status]').forEach(function (item) {
    var status = item.getAttribute('data-task-status');
    var searchText = item.getAttribute('data-task-search') || '';

    var statusMatch = statusFilter === 'all' || status === statusFilter;
    var searchMatch = !search || searchText.indexOf(search) !== -1;

    if (statusMatch && searchMatch) {
      item.classList.remove('filter-hidden');
    } else {
      item.classList.add('filter-hidden');
    }
  });

  // Hide sidebar epic sections with no visible tasks, or completed when toggle is off
  document.querySelectorAll('.nav-section[data-epic]').forEach(function (section) {
    var epicId = section.getAttribute('data-epic');
    var mainEpic = document.getElementById(epicId);
    var epicStatus = mainEpic ? mainEpic.getAttribute('data-epic-status') : null;
    var allTasks = section.querySelectorAll('.nav-task-item');
    var visibleTasks = section.querySelectorAll('.nav-task-item:not(.filter-hidden)');
    if (hideCompletedEpics && epicStatus === 'COMPLETED') {
      section.classList.add('filter-hidden');
    } else if (allTasks.length > 0 && visibleTasks.length === 0) {
      section.classList.add('filter-hidden');
    } else {
      section.classList.remove('filter-hidden');
    }
  });
}

function initFilters() {
  // Search input
  var searchEl = document.getElementById('filterSearch');
  if (searchEl) {
    searchEl.addEventListener('input', applyFilters);
  }

  // Status chips
  document.querySelectorAll('.filter-chip').forEach(function (chip) {
    chip.addEventListener('click', function () {
      var filter = chip.getAttribute('data-filter');

      // Toggle: clicking active chip resets to 'all'
      if (_activeFilter === filter && filter !== 'all') {
        _activeFilter = 'all';
      } else {
        _activeFilter = filter;
      }

      // Update active class
      document.querySelectorAll('.filter-chip').forEach(function (c) {
        c.classList.remove('active');
      });
      document.querySelector('.filter-chip[data-filter="' + _activeFilter + '"]').classList.add('active');

      applyFilters();
    });
  });

  // Show completed epics checkbox
  var showCompletedEl = document.getElementById('filterShowCompleted');
  if (showCompletedEl) {
    showCompletedEl.addEventListener('change', applyFilters);
  }
}

// ══════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function () {
  var data = loadData();
  buildTaskIndex(data);
  renderSidebar(data);
  renderContent(data);
  initEpicToggles();
  initTaskClicks();
  initModal();
  initFilters();
  collapseCompletedEpics();
  initMobileSidebar();
  initScrollSpy();
});
