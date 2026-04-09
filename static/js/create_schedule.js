function fillScheduleIntermediateTables() {
        check_validation();
        let employees = document.getElementById("employees-select");
        let tasks = document.getElementById("tasks-select");
        let employeeTable = document.getElementById("employee-table").getElementsByTagName('tbody')[0];
        let taskTable = document.getElementById("task-table").getElementsByTagName('tbody')[0];

        // Clear existing rows
        employeeTable.innerHTML = '';
        taskTable.innerHTML = '';

        // Calculate Schedule duration
        const scheduleTime = getWorkingHours(document.getElementById('start_time').value, document.getElementById('end_time').value);


        // Add a row for each selected employee
        for (let i = 0; i < employees.options.length; i++) {
            if (employees.options[i].selected) {
                let row = employeeTable.insertRow(-1);
                let cell0 = row.insertCell(0);
                let cell1 = row.insertCell(1);
                let cell2 = row.insertCell(2);
                let cell3 = row.insertCell(3);
                let cell4 = row.insertCell(4);

             	row.setAttribute("data-employee-id", employees.options[i].value)
                cell0.innerHTML = employees.options[i].value;
                cell0.hidden = true;
                cell1.innerHTML = employees.options[i].text;
                const calculatedTimeField = document.createElement('input');
                calculatedTimeField.type = 'time';
                cell4.appendChild(calculatedTimeField);
                calculatedTimeField.value = scheduleTime;
                calculatedTimeField.required = true;
                const hh=0;
                const mm = 0;
                cell3.innerHTML = `${hh.toString().padStart(2, '0')}:${mm.toString().padStart(2, '0')}`;  // Initial assigned time set to 0
                cell2.innerHTML = employees.options[i].dataset.rank;
                }
        }
        // Add a row for each selected task
        for (let i = 0; i < tasks.options.length; i++) {
            if (tasks.options[i].selected) {
                let row = taskTable.insertRow(-1);
                let cell0 = row.insertCell(0);
                let cell1 = row.insertCell(1);
                let cell2 = row.insertCell(2);
                let cell3 = row.insertCell(3);
                let cell4 = row.insertCell(4);

                row.setAttribute("data-task-id", tasks.options[i].value)
                cell0.innerHTML = tasks.options[i].value;
                cell0.hidden = true;
                cell1.innerHTML = tasks.options[i].text;
                const calculatedTimeField = document.createElement('input');
                calculatedTimeField.type = 'time';
                calculatedTimeField.required = true;
                calculatedTimeField.value = "01:00";
                cell4.appendChild(calculatedTimeField);
                const taskHH =0;
                const taskMM  = 0;
                cell3.innerHTML = `${taskHH.toString().padStart(2, '0')}:${taskMM.toString().padStart(2, '0')}`;
                cell2.innerHTML = tasks.options[i].dataset.responsibility_level;
            }
        }
    }

    // Function to calculate working hours based on start and end time
    function getWorkingHours(startTime, endTime) {
        let startDateTime = new Date('1970-01-01T' + startTime);
        let endDateTime = new Date('1970-01-01T' + endTime);
        let diffMinutes = (endDateTime - startDateTime) / (1000 * 60);
        const hours = Math.floor(diffMinutes / 60);
        const minutes = diffMinutes % 60;
        const formattedTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;

        return formattedTime;
        }


	// Function to convert minutes to 'HH:MM' strings
	function minutesToTimeString(diffMinutes){
		const hours = Math.floor(diffMinutes / 60);
        const minutes = diffMinutes % 60;
        const formattedTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;

        return formattedTime;

	}


	// Function to convert 'HH:MM' strings to minutes
	function timeStringToMinutes(timeStr) {
      // Basic input validation
      if (!timeStr || typeof timeStr !== 'string') {
        return null; // Or throw an error based on your preference
      }

      const timeParts = timeStr.split(':');
      if (timeParts.length !== 2) {
        return null; // Invalid format
      }

      const [hours, minutes] = timeParts;
      if (isNaN(parseInt(hours)) || isNaN(parseInt(minutes))) {
        return null; // Non-numeric values
      }

      return parseInt(hours) * 60 + parseInt(minutes);
    }


	// Function to extract employee data from the HTML table
	function extractEmployees() {
    let employeeRows = document.getElementById("employee-table").getElementsByTagName('tbody')[0].getElementsByTagName('tr');

    let employees = [];

    for (let i = 0; i < employeeRows.length; i++) {
        let cells = employeeRows[i].getElementsByTagName('td');
        employees.push({
            employee_id: parseInt(cells[0].innerHTML),
            employee_name: cells[1].innerHTML,
            employee_rank: parseInt(cells[2].innerHTML),
            total_assigned_hours: timeStringToMinutes(cells[3].innerHTML),
            working_hours: timeStringToMinutes(cells[4].getElementsByTagName('input')[0].value),
        });
    }

    return employees;
}

	// Function to extract task data from the HTML table
    function extractTasks() {
      let taskRows = document.getElementById("task-table").getElementsByTagName('tbody')[0].getElementsByTagName('tr');
      let tasks = [];

      for (let i = 0; i < taskRows.length; i++) {
        let cells = taskRows[i].getElementsByTagName('td');
        let total_assigned_time = timeStringToMinutes(cells[3].innerHTML);
        let total_duration = timeStringToMinutes(cells[4].getElementsByTagName('input')[0].value);

        // Check if both times are valid
        if (total_assigned_time !== null && total_duration !== null) {
          tasks.push({
            task_id: parseInt(cells[0].innerHTML),
            task_name: cells[1].innerHTML,
            responsibility_level: parseInt(cells[2].innerHTML),
            total_assigned_time: total_assigned_time,
            total_duration: total_duration,
          });
        }
      }

      return tasks;
    }

	// Function to calculate assigned times
		function calculateTimes(scheduleItems, tasks, employees) {
		  // Reset task and employee times before calculations
		  for (const task of tasks) {
			task.total_assigned_time = 0;
		  }
		  for (const employee of employees) {
			employee.total_assigned_hours = 0;
		  }

		  // Calculate times based on scheduleItems
		  for (const scheduleItem of scheduleItems) {
		  //if scheduleItem.assigned_time
			const task = tasks.find(task => task.task_id === scheduleItem.task_id);
			const employee = employees.find(employee => employee.employee_id === scheduleItem.employee_id);

			  task.total_assigned_time += scheduleItem.assigned_time;
			  employee.total_assigned_hours += scheduleItem.assigned_time;
			}
		}

		function getOrCreateScheduleItem(task, employee, scheduleItems, assigned_time=0) {
		  for (const scheduleItem of scheduleItems) {
			if (scheduleItem.task_id === task.task_id && scheduleItem.employee_id === employee.employee_id) {
			  return { scheduleItem: scheduleItem, created: false }; // Return existing item
			}
		  }

			newscheduleItem = { task_id: parseInt(task.task_id),
								task_name: task.task_name,
								employee_id: parseInt(employee.employee_id),
								employee_name: employee.employee_name,
								assigned_time: parseInt(assigned_time),
								};

			return {scheduleItem: newscheduleItem, created : true };

		}

        //Function to distribute tasks to eligible employees
        function distributeTasks() {
        check_validation();
        let tasks = extractTasks();
		let employees = extractEmployees();


		  let scheduleItems = [];

		  for (let i = 0; i < tasks.length; i++) {
			let task = tasks[i];
			let duration = task.total_duration - task.total_assigned_time;

			let eligibleEmployees = employees.filter(function(employee) {
			  return (employee.employee_rank <= task.responsibility_level &&
			  (employee.working_hours - employee.total_assigned_hours) > 0
			  );
			});

			let tempAssignedHours = 0;

			while (duration > 0 && eligibleEmployees.length > 0) {
			  let perEmployeeDuration = duration / eligibleEmployees.length;
			  let assignedAnyTime = false;

			  for (let j = 0; j < eligibleEmployees.length; j++) {
				let employee = eligibleEmployees[j];
				let assignedTime = Math.min(perEmployeeDuration, (employee.working_hours - employee.total_assigned_hours));
				if (assignedTime > 0) {
					duration -= assignedTime;
					tempAssignedHours += assignedTime; // Update temporary variable
					const { scheduleItem, created } = getOrCreateScheduleItem(task, employee, scheduleItems);
					scheduleItem.assigned_time = assignedTime;
					if (created) {
						scheduleItems.push(scheduleItem);
					  }

					 assignedAnyTime = true;

					}

					// Reassess eligible employees and redistribute remaining duration if needed
					//check again
					if (tempAssignedHours  >= (employee.working_hours)) {
					  eligibleEmployees.splice(j, 1);

					  j--; // Adjust index after removing an item

					  perEmployeeDuration = duration / eligibleEmployees.length;
					  break; // Re-enter the loop with updated values
					}

				}
				// Exit outer loop if no time was assigned in this iteration
                  if (!assignedAnyTime) {
                    break;
                  }
			}

			calculateTimes(scheduleItems, tasks, employees)
		  }
			fillScheduleItemsTable(scheduleItems);
			updateTables();

    }

	    function fillScheduleItemsTable(scheduleItems) {
            const scheduleTable = document.getElementById("scheduleItems-table");
            const tableBody = scheduleTable.getElementsByTagName('tbody')[0];
            const tableFooter = scheduleTable.createTFoot(); // Create the footer if it doesn't exist
            const employees = document.getElementById("employees-select"); // employees main select
            const tasks = document.getElementById("tasks-select"); // tasks main select

			tableBody.innerHTML = '';

			// Iterate through scheduleItems and create table rows
			scheduleItems.forEach(scheduleItem => {
			  const row = document.createElement("tr");

			  // Task ID (hidden)
			  const taskIdCell = document.createElement("td");
			  taskIdCell.textContent = scheduleItem.task_id;
			  taskIdCell.style.display = "none"; // Hide the cell
			  row.appendChild(taskIdCell);

			  // Task Name
			  const taskNameCell = document.createElement("td");
			  taskNameCell.textContent = scheduleItem.task_name;
			  row.appendChild(taskNameCell);

			  // Employee ID (hidden)
			  const employeeIdCell = document.createElement("td");
			  employeeIdCell.textContent = scheduleItem.employee_id;
			  employeeIdCell.style.display = "none"; // Hide the cell
			  row.appendChild(employeeIdCell);

			  // Employee Name
			  const employeeNameCell = document.createElement("td");
			  employeeNameCell.textContent = scheduleItem.employee_name;
			  row.appendChild(employeeNameCell);

			  // Assigned Time (input field)
			  const assignedTimeCell = document.createElement("td");
			  const assignedTimeInput = document.createElement("input");
			  assignedTimeInput.type = "time";
			  assignedTimeInput.value = minutesToTimeString(scheduleItem.assigned_time); // Set initial value
			  assignedTimeInput.addEventListener("change", (event) => {
			  updateTables();
			  });
			  assignedTimeCell.appendChild(assignedTimeInput);
			  row.appendChild(assignedTimeCell);

			  // Action (reset button)
			  const actionCell = document.createElement("td");
			  const deleteButton = document.createElement("button");
			  deleteButton.type = "button"
			  deleteButton.textContent = "Delete";

			  actionCell.appendChild(deleteButton);
			  row.appendChild(actionCell);
			  deleteButton.addEventListener("click", (event) => {
                // Find the row containing this button and remove it
                const rowToDelete = event.target.closest('tr');
                if (rowToDelete) {
                    rowToDelete.remove();
                }
			  });

			  // Append the row to the table body
			  tableBody.appendChild(row);
			});
			tableFooter.innerHTML = ''; // clear the footer
			// Create the addition row with all fields

            const additionRow = document.createElement("tr");

            // Task ID (hidden)
            const taskIdCell = document.createElement("td");
            taskIdCell.style.display = "none"; // Hide the cell
            additionRow.appendChild(taskIdCell);

            // Task Name
            const taskNameCell = document.createElement("td");
            const taskSelect = document.createElement("select");
            additionRow.appendChild(taskNameCell);
            taskNameCell.appendChild(taskSelect);

             // Populate the multi-select with employees
            for (let i = 0; i < tasks.options.length; i++) {
              if (tasks.options[i].selected) {
              const taskOption = document.createElement("option");
              taskOption.value = tasks.options[i].value;
              taskOption.text = tasks.options[i].text;
              taskSelect.appendChild(taskOption);
              }
            }

            // Employee ID (hidden)
            const employeeIdCell = document.createElement("td");
            employeeIdCell.style.display = "none"; // Hide the cell
            additionRow.appendChild(employeeIdCell);

            // Employee Cell (multi-select)
            const employeeCell = document.createElement("td");
            const employeeSelect = document.createElement("select");
            additionRow.appendChild(employeeCell);
            employeeCell.appendChild(employeeSelect);

            // Populate the multi-select with employees
            for (let i = 0; i < employees.options.length; i++) {
              if (employees.options[i].selected) {
              const employeeOption = document.createElement("option");
              employeeOption.value = employees.options[i].value; // Assuming value contains ID
              employeeOption.text = employees.options[i].text;
              employeeSelect.appendChild(employeeOption);
              }

            }

            // Assigned Time
            const assignedTimeCell = document.createElement("td");
            const assignedTimeInput = document.createElement("input");
            assignedTimeInput.type = "time";
            assignedTimeInput.value = minutesToTimeString(0); // Set initial value
            assignedTimeCell.appendChild(assignedTimeInput);
            additionRow.appendChild(assignedTimeCell);

            // Action (Add button)
            const actionCell = document.createElement("td");
            const addButton = document.createElement("button");
            addButton.type = "button"; // Set button type to prevent form submission
            addButton.textContent = "Add"; // Button text

            actionCell.appendChild(addButton);
            additionRow.appendChild(actionCell);

            // Append the addition row to the table footer
            tableFooter.appendChild(additionRow);

            // Add event listener to the add button
            addButton.addEventListener("click", function() {
                addNewScheduleItemRow(additionRow); // Pass additionRow as a parameter
            });

		}

		// Function to add a new row to the scheduleItems table
        function addNewScheduleItemRow(additionRow) { // Receive additionRow as a parameter

            const tableBody = document.getElementById("scheduleItems-table").getElementsByTagName("tbody")[0];


            // Get the selected task and employee from the dropdowns
            const selectedTaskId = additionRow.cells[1].querySelector("select").value;
            const selectedTaskName = additionRow.cells[1].querySelector("select option:checked").textContent;
            const selectedEmployeeId = additionRow.cells[3].querySelector("select").value;
            const selectedEmployeeName = additionRow.cells[3].querySelector("select option:checked").textContent;

            // Get the time from the footer row
            const assignedTime = additionRow.querySelector("input[type='time']").value;

            // Create a new row for the scheduleItems table
            const newRow = document.createElement("tr");

            // Populate the new row with cell data
            newRow.innerHTML = `
                <td style="display:none">${selectedTaskId}</td>
                <td>${selectedTaskName}</td>
                <td style="display:none">${selectedEmployeeId}</td>
                <td>${selectedEmployeeName}</td>

            `;
            // Assigned Time (input field)
            const assignedTimeCell = document.createElement("td");
            const assignedTimeInput = document.createElement("input");
            assignedTimeInput.type = "time";
            assignedTimeInput.value = assignedTime; // Set value to the assigned time
            assignedTimeCell.appendChild(assignedTimeInput);
            newRow.appendChild(assignedTimeCell);

            // Action (Reset button)
            const actionCell = document.createElement("td");
            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.textContent = "Delete";
            actionCell.appendChild(deleteButton);
            newRow.appendChild(actionCell);
            deleteButton.addEventListener("click", (event) => {
    // Find the row containing this button and remove it
    const rowToDelete = event.target.closest('tr');
    if (rowToDelete) {
        rowToDelete.remove();
    }
});


            // Add the new row to the table body
            tableBody.appendChild(newRow);

            // Call the updateTables function to update the tables
            updateTables();
        }
		function createScheduleItemsFromTable(tableId) {
		  const scheduleItems = [];
		  const table = document.getElementById(tableId);
		  const tableRows = table.querySelectorAll("tbody tr");

		  for (const row of tableRows) {
			const cells = row.querySelectorAll("td");
			const taskId = cells[0].textContent;
			const taskName = cells[1].textContent;
			const employeeId = cells[2].textContent;
			const employeeName = cells[3].textContent;
			// Check for valid time format HH:MM
			const timeInput = cells[4].querySelector("input").value;
			// Validate time format
            const timeRegex = /^\d{2}:\d{2}$/;
            if (!timeRegex.test(timeInput) || timeInput === "--:--" || timeInput === "00:00") {
              // Handle invalid time input
              console.error("Invalid time input:", timeInput);
              continue; // Skip this row
            }
			const assignedTime = timeStringToMinutes(timeInput);

			const scheduleItem = {
			  task_id: parseInt(taskId),
			  task_name: taskName,
			  employee_id: parseInt(employeeId),
			  employee_name: employeeName,
			  assigned_time: assignedTime
			};

			scheduleItems.push(scheduleItem);
		  }

		  return scheduleItems;
		}

		// Update tables function
		function updateTables(){
			const tasks = extractTasks();
			const employees = extractEmployees();
			const scheduleItems = createScheduleItemsFromTable("scheduleItems-table");

			// Caluculating new times
			calculateTimes(scheduleItems, tasks, employees);

			// Update employee table
			const employeeTable = document.getElementById("employee-table");
			for (const employee of employees) {
				const employeeRow = employeeTable.querySelector(`tbody tr[data-employee-id="${employee.employee_id}"]`);
				if (employeeRow) {
				const assignedTimeCell = employeeRow.querySelector("td:nth-child(4)");
				assignedTimeCell.textContent = minutesToTimeString(employee.total_assigned_hours); // Update Assigned Time
				assignedTimeCell.style.color = employee.total_assigned_hours > employee.working_hours ? "red" : ""; // Apply red color if exceeded

				}
			}

			// Update task table
			const taskTable = document.getElementById("task-table");
			for (const task of tasks) {
			const taskRow = taskTable.querySelector(`tbody tr[data-task-id="${task.task_id}"]`);
			if (taskRow) {
			  const assignedTimeCell = taskRow.querySelector("td:nth-child(4)");
				assignedTimeCell.textContent = minutesToTimeString(task.total_assigned_time); // Update Assigned Time
				assignedTimeCell.style.color = task.total_assigned_time > task.total_duration ? "red" : ""; // Apply red color if exceeded
				}
		  }
		}
                // post method to server
        function submitData() {
            const form = document.getElementById("main-form");
            if (form.checkValidity() && check_validation()){
                const schedule_name = document.getElementById("schedule_name").value;
                const start_time = document.getElementById("start_time").value;
                const end_time = document.getElementById("end_time").value;
                const formData = new FormData();
                const tasks = extractTasks();
                const employees = extractEmployees();
                const scheduleItems = createScheduleItemsFromTable("scheduleItems-table");
                if (scheduleItems.length>0){
                    // Add tasks, employees, and scheduleItems as JSON strings
                    formData.append("tasks", JSON.stringify(tasks));
                    formData.append("employees", JSON.stringify(employees));
                    formData.append("scheduleItems", JSON.stringify(scheduleItems));
                    formData.append("schedule_name", schedule_name);
                    formData.append("start_time", start_time);
                    formData.append("end_time", end_time);
                    showLoadingContainer();
                    // Send the form data using AJAX to the Django view URL
                    fetch("/schedule/create_schedule/", {
                        method: "POST",
                        body: formData,
                        headers: {
                            'X-CSRFToken': getCookie('csrftoken') // Include CSRF token for Django
                            }
                        })
                        .then(response => response.json())
                        .then(data => {
                            hideLoadingContainer()
                            if (data.success) {
                                const message = "TRT Type creer avec success, voulez vouz quiter le menu creation?";
                                const confirmed = confirm(message);
                                if (confirmed) {
                                    if (data.url) {
                                        window.location.href = data.url;
                                        }else {
                                            window.location.reload();
                                            }
                                }else {
                                    window.location.reload();
                                    }
                            }else {
                                console.log(response.data);
                                }
                            })
                            .catch(error => {
                                // Handle errors
                                });
                }else {
                    alert('Aucune assignation!');
                    }
            }
            else {
                // Handle invalid form
                form.reportValidity()
                //alert("La form n'est pas valide");
                }

        }


        // Helper function to get the CSRF token from a cookie
        function getCookie(name) {
          let cookieValue = null;
          if (document.cookie && document.cookie !== '') {
            let cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
              let cookie = cookies[i].trim();
              if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
              }
            }
          }
          return cookieValue;
        }

function check_validation(){
    const form = document.getElementById("main-form");

    if ($('#employees-select option:selected').length <= 0 || $('#tasks-select option:selected').length <= 0) {
        alert("Selectionnez des Taches et des Employees pour la distribution!");

        form.reportValidity()
        return false
        }
    else{
          form.reportValidity()
          return true
    }
}

    function selectTasksByType(taskType) {
        $('#tasks-select option').each(function() {
            if ($(this).closest('optgroup').attr('label') === 'AUTO') {
                $(this).prop('selected', true); // Select options of the given type
                $('#tasks-select').trigger('chosen:updated');
            }
        });
    }

        function addEmployeesFromGroup() {
        var selectedTeam = $('#team-select').val();
        var teamMembers = $('#team-select').find(':selected').data('members');

        if (teamMembers) {
            var membersArray = teamMembers.split(',');
            membersArray.forEach(function(member) {
                $('#employees-select option').each(function() {
                    if ($(this).val() == member) {
                        $(this).prop('selected', true);
                        $('#employees-select').trigger('chosen:updated');

                    }
                });
            });
        }
    }