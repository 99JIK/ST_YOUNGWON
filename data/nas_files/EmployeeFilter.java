// EmployeeFilter.java
import java.util.*;
import java.util.function.Predicate;
import java.util.stream.Collectors;

public class EmployeeFilter {

    public List<Employee> filterAndSort(List<Employee> list, double min, double max) {
        Predicate<Employee> range = e -> e.getSalary() >= min && e.getSalary() <= max;

        return list.stream()
                .filter(range)
                .sorted(Comparator.comparing(Employee::getLastName)
                                  .thenComparing(Employee::getFirstName))
                .collect(Collectors.toList());
    }
}