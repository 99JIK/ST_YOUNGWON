// StringProcessor.java
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class StringProcessor {

    public List<String> process(String[] inputs, int length) {
        return Arrays.stream(inputs)
                .filter(s -> s.length() >= length)
                .map(String::toUpperCase)
                .sorted()
                .collect(Collectors.toList());
    }
}