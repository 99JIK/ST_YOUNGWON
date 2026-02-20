// DepartmentAnalyzer.java
import java.util.*;
import java.util.stream.Collectors;

public class DepartmentAnalyzer {

    public Map<String, Long> countByDepartment(List<Employee> list) {
        return list.stream()
                .collect(Collectors.groupingBy(Employee::getDepartment, Collectors.counting()));
    }
}