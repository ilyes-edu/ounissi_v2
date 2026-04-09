// Example usage for tasks select:
//toggleOptgroupOptions(document.getElementById('select_id'), 'group_class');
function toggleOptgroupOptions(selectElement, optgroupClass) {
    selectElement.addEventListener('click', (event) => {
        const clickedElement = event.target;

        if (clickedElement.classList.contains(optgroupClass)) {
            const optgroup = clickedElement;
            const options = optgroup.querySelectorAll('option');

            options.forEach((option) => {
                option.selected = !option.selected;
            });
        }
    });
}
        function distributeLines(list) {
            const numberOfLinesInput = document.getElementById('number_of_lines');
            const employee1Select = document.getElementById('employee1');
            const employee2Select = document.getElementById('employee2');
            const employee3Select = document.getElementById('employee3');
            const start1Input = document.getElementById('start1');
            const end1Input = document.getElementById('end1');
            const start2Input = document.getElementById('start2');
            const end2Input = document.getElementById('end2');
            const start3Input = document.getElementById('start3');
            const end3Input = document.getElementById('end3');
            const numberOfLines = parseInt(numberOfLinesInput.value);
            let number1 = document.getElementById('number1');
//            let time1 = document.getElementById('item1_time');

            let number2 = document.getElementById('number2');
            let number3 = document.getElementById('number3');
            let duration = 0
//            let lower = 0
//            let upper = 0;
            number1.innerText = number2.innerText = number3.innerText = '--:--:--'
            let duplicate2 = false;
            let duplicate3 = false;
            start2Input.value = end2Input.value = start3Input.value = end3Input.value = '';
            if (employee1Select.value === employee2Select.value){
            duplicate2 = true;
            }
            if ((employee2Select.value === employee3Select.value) || (employee1Select.value === employee3Select.value)){
            duplicate3 = true;
            }

            if (numberOfLines && numberOfLines > 0) {
                if (list.length === 1){
                    for (let i = 1; i <= numberOfLines-1; i++) {
                        list[i] = list[0];
                      }
                }
                // Calculate ranges based on number of employees selected
                if ((employee1Select.value && !employee2Select.value) || (employee1Select.value && duplicate2)){
                    // Only employee 1 selected
                    start1Input.value = 1;
                    end1Input.value = numberOfLines;
                    duration = sumBetweenIndexes(list, start1Input.value-1, end1Input.value-1)
                    console.log('seconds', duration);
                    console.log(secondsToHms(duration))
                    number1.innerText = secondsToHms(duration)
                } else if ((employee1Select.value && employee2Select.value && !employee3Select.value && numberOfLines >2) || (employee1Select.value && employee2Select.value && numberOfLines >2 && duplicate3)){
                    // Employee 1 and 2 selected
                    const linesPerEmployee = Math.ceil(numberOfLines / 2);
                    start1Input.value = 1;
                    end1Input.value = linesPerEmployee;
                    start2Input.value = linesPerEmployee + 1;
                    end2Input.value = numberOfLines;
                    duration = sumBetweenIndexes(list, start1Input.value-1, end1Input.value-1);
                    item1_time.value = duration;
                    number1.innerText = secondsToHms(duration);
                    duration = sumBetweenIndexes(list, start2Input.value-1, end2Input.value-1);
                    number2.innerText = secondsToHms(duration);
                } else if (employee1Select.value && employee2Select.value && employee3Select.value && numberOfLines > 3 && !duplicate3) {
                    // All three employees selected
                    const linesPerEmployee = Math.ceil(numberOfLines / 3);
                    start1Input.value = 1;
                    end1Input.value = linesPerEmployee;
                    start2Input.value = linesPerEmployee + 1;
                    end2Input.value = linesPerEmployee + Math.ceil((numberOfLines - linesPerEmployee) / 2);
                    start3Input.value = (linesPerEmployee + Math.ceil((numberOfLines - linesPerEmployee) / 2)) + 1;
                    end3Input.value = numberOfLines;
                    duration = sumBetweenIndexes(list, start1Input.value-1, end1Input.value-1)
                    number1.innerText = secondsToHms(duration)
                    duration = sumBetweenIndexes(list, start2Input.value-1, end2Input.value-1)
                    number2.innerText = secondsToHms(duration)
                    duration = sumBetweenIndexes(list, start3Input.value-1, end3Input.value-1)
                    number3.innerText = secondsToHms(duration)
                }
            }
        }

	function timeStringToSeconds(timeStr) {
      const timeParts = timeStr.split(':');

      const [hours, minutes, seconds] = timeParts;

      return parseInt(hours) * 3600 + parseInt(minutes) * 60 + parseInt(seconds);
    }
    function secondsToHms(seconds) {
        const pad = (num, size) => ("00" + num).slice(-size);
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secondsLeft = seconds % 60;

    return `${pad(hours, 2)}:${pad(minutes, 2)}:${pad(secondsLeft, 2)}`;
}

    function sumBetweenIndexes(list, lower, upper) {
      let sum = 0;
      for (let i = lower; i <= upper; i++) {
        sum += parseInt(list[i], 10);
      }
    return sum;
}
