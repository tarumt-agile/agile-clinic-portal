(function () {
  "use strict";

  const STATUS_COLORS = {
    scheduled: "#4f46e5",
    completed: "#059669",
    cancelled: "#94a3b8",
  };

  function initScheduleCalendar(config) {
    const el = document.getElementById(config.containerId);
    if (!el || !window.FullCalendar) return null;

    const calendar = new FullCalendar.Calendar(el, {
      initialView: localStorage.getItem(config.calendarViewStorageKey) || "dayGridMonth",
      headerToolbar: {
        left: "prev,next today",
        center: "title",
        right: "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
      },
      height: "auto",
      events: function (info, successCallback, failureCallback) {
        const startDate = info.startStr.slice(0, 10);
        const endDate = info.endStr.slice(0, 10);
        fetch(config.eventsUrl(startDate, endDate))
          .then((response) => {
            if (!response.ok) throw new Error("Request failed");
            return response.json();
          })
          .then((data) => {
            const events = data.appointments.map((a) => {
              const color = STATUS_COLORS[a.status] || "#64748b";
              const suffix = a.status === "cancelled" ? " (Cancelled)" : "";
              return {
                id: a.reference_number,
                title: a.start_time.slice(0, 5) + " " + a.patient_name + suffix,
                start: a.appointment_date + "T" + a.start_time,
                end: a.appointment_date + "T" + a.end_time,
                backgroundColor: color,
                borderColor: color,
                extendedProps: a,
              };
            });
            successCallback(events);
          })
          .catch(failureCallback);
      },
      eventClick: function (clickInfo) {
        if (config.onEventClick) config.onEventClick(clickInfo.event.extendedProps);
      },
      viewDidMount: function (arg) {
        localStorage.setItem(config.calendarViewStorageKey, arg.view.type);
      },
    });

    calendar.render();
    return calendar;
  }

  function initScheduleViewToggle(config) {
    const listViewEl = document.getElementById(config.listViewId);
    const calendarViewEl = document.getElementById(config.calendarViewId);
    const listButton = document.getElementById(config.listButtonId);
    const calendarButton = document.getElementById(config.calendarButtonId);
    let calendarInstance = null;

    function showList() {
      listViewEl.classList.remove("d-none");
      calendarViewEl.classList.add("d-none");
      listButton.classList.add("active");
      calendarButton.classList.remove("active");
      localStorage.setItem(config.viewModeStorageKey, "list");
    }

    function showCalendar() {
      listViewEl.classList.add("d-none");
      calendarViewEl.classList.remove("d-none");
      calendarButton.classList.add("active");
      listButton.classList.remove("active");
      localStorage.setItem(config.viewModeStorageKey, "calendar");
      if (!calendarInstance) {
        calendarInstance = initScheduleCalendar(config.calendar);
      } else {
        calendarInstance.updateSize();
      }
    }

    listButton.addEventListener("click", showList);
    calendarButton.addEventListener("click", showCalendar);

    if (localStorage.getItem(config.viewModeStorageKey) === "calendar") {
      showCalendar();
    } else {
      showList();
    }

    return {
      refresh: function () {
        if (calendarInstance) calendarInstance.refetchEvents();
      },
    };
  }

  window.initScheduleViewToggle = initScheduleViewToggle;
})();
